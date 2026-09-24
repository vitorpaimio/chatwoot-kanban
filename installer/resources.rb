# Adaptador administrativo. Não registrar request/result: podem conter token.
require 'securerandom'
require 'json'
result = {}
ActiveRecord::Base.transaction do
  ActiveRecord::Base.connection.execute('SET TRANSACTION READ ONLY') if request['operation'] == 'inspect'
  ActiveRecord::Base.connection.execute('SELECT pg_advisory_xact_lock(741825)')
  accounts = request.fetch('accounts').sort
  accounts.each { |id| Account.find(id) }
  registry = InstallationConfig.find_or_initialize_by(name: 'KANBAN_INSTALLER_V1')
  state = registry.persisted? ? JSON.parse(registry.value) : { 'installations' => {} }
  installations = state.fetch('installations')
  identity = request.fetch('identity')
  operation = request.fetch('operation')
  entry = installations[identity]
  if operation == 'inspect'
    result['accounts'] = accounts.to_h do |id|
      [id.to_s, Account.find(id).custom_attribute_definitions.map do |attribute|
        attribute.attributes.slice('id', 'attribute_key', 'attribute_model',
                                   'attribute_display_type', 'attribute_values')
      end]
    end
    result['receipt'] = entry
  elsif operation == 'install'
    installations.each do |key, other|
      next if key == identity || other['status'] == 'removed'
      raise 'Conta já gerenciada por outra instalação' if (other['accounts'] & accounts).any?
    end
    raise 'Seleção de contas mudou' if entry && entry['accounts'] != accounts
    entry ||= { 'accounts' => accounts, 'attributes' => [], 'webhooks' => [] }
    user = User.find_by(id: entry['user_id']) if entry['status'] != 'removed'
    if user
      raise 'Vínculo técnico alterado' unless user.account_users.pluck(:account_id).sort == accounts && user.account_users.all?(&:administrator?)
    else
      email = "kanban-#{identity}@service.invalid"
      raise 'Usuário alheio com mesmo nome' if User.exists?(email: email)
      password = SecureRandom.hex(48) + 'Aa1!'
      user = User.new(name: "Serviço Kanban #{request.fetch('name')}", email: email,
                      password: password, password_confirmation: password)
      user.skip_confirmation!
      user.save!
      accounts.each { |id| AccountUser.create!(account_id: id, user: user, role: :administrator) }
      entry['user_id'] = user.id
    end
    accounts.each do |id|
      account = Account.find(id)
      request.fetch('attributes').each do |payload|
        attribute = account.custom_attribute_definitions.find_by(
          attribute_key: payload.fetch('attribute_key'), attribute_model: 1)
        previous = entry['attributes'].find { |a| a['account'] == id && a['id'] == attribute&.id }
        created = attribute.nil?
        attribute ||= account.custom_attribute_definitions.create!(payload)
        expected_type = CustomAttributeDefinition.attribute_display_types.key(payload.fetch('attribute_display_type'))
        raise 'Conflito de tipo' unless attribute.attribute_display_type == expected_type
        receipt = { 'account' => id, 'id' => attribute.id,
                    'key' => attribute.attribute_key, 'type' => expected_type,
                    'ownership' => previous&.fetch('ownership') || (created ? 'created' : 'preexisting') }
        entry['attributes'].reject! { |a| a['account'] == id && a['key'] == attribute.attribute_key }
        entry['attributes'] << receipt
      end
      url = request.fetch('callback') + "/kanban/webhooks/#{id}/events"
      hook = account.webhooks.find_by(url: url)
      previous = entry['webhooks'].find { |h| h['account'] == id && h['id'] == hook&.id }
      created = hook.nil?
      hook ||= account.webhooks.create!(url: url, subscriptions: %w[contact_created contact_updated conversation_created conversation_updated conversation_status_changed])
      entry['webhooks'].reject! { |h| h['account'] == id && h['url'] == url }
      entry['webhooks'] << { 'account' => id, 'id' => hook.id, 'url' => url,
                            'ownership' => previous&.fetch('ownership') || (created ? 'created' : 'preexisting') }
    end
    loader = '<script data-chatwoot-kanban src="/kanban/loader.js" defer></script>'
    scripts = InstallationConfig.find_or_initialize_by(name: 'DASHBOARD_SCRIPTS')
    unless scripts.value.to_s.include?('data-chatwoot-kanban')
      scripts.value = scripts.value.to_s + "\n" + loader
      scripts.save!
      state['loader_created'] = true
    end
    entry['status'] = 'installed'
    installations[identity] = entry
    registry.value = JSON.generate(state)
    registry.save!
    result = { 'receipt' => entry, 'token' => user.access_token.token }
  elsif operation == 'uninstall'
    if entry && entry['status'] != 'removed'
      raise 'Seleção de contas mudou' unless entry['accounts'] == accounts
      entry['webhooks'].each do |h|
        next unless h['ownership'] == 'created'
        hook = Account.find(h['account']).webhooks.find_by(id: h['id'])
        hook.destroy! if hook && hook.url == h['url']
      end
      if request['purge']
        entry['attributes'].each do |a|
          next unless a['ownership'] == 'created'
          attribute = Account.find(a['account']).custom_attribute_definitions.find_by(id: a['id'])
          if attribute && attribute.attribute_key == a['key'] && attribute.attribute_display_type == a['type'] && attribute.attribute_model == 'contact_attribute'
            attribute.destroy!
          end
        end
      end
      user = User.find_by(id: entry['user_id'])
      if user
        raise 'Usuário técnico alterado; revogação requer revisão' unless user.email == "kanban-#{identity}@service.invalid" && (user.account_users.pluck(:account_id) - accounts).empty?
        user.access_token&.destroy!
        user.account_users.destroy_all
        user.tokens = {}
        user.save!
        user.destroy!
      end
      entry['status'] = 'removed'
      if state['loader_created'] && installations.values.none? { |v| v['status'] != 'removed' }
        scripts = InstallationConfig.find_by(name: 'DASHBOARD_SCRIPTS')
        if scripts
          scripts.value = scripts.value.to_s.gsub('<script data-chatwoot-kanban src="/kanban/loader.js" defer></script>', '')
          scripts.save!
        end
        state['loader_created'] = false
      end
      registry.value = JSON.generate(state)
      registry.save!
    end
    result = { 'receipt' => entry }
  else
    raise 'Operação inválida'
  end
end
puts 'KANBAN_RESULT=' + JSON.generate(result)
