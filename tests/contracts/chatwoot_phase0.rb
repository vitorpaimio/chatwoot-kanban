# Execute com rails runner em uma cópia oficial isolada, nunca na instalação ativa.
require 'json'
require 'securerandom'
require 'stringio'
require 'openssl'

abort 'Exige Rails test e Community Edition' unless Rails.env.test? && !ChatwootApp.enterprise?
database = ActiveRecord::Base.connection_db_config.database
abort 'Banco não autorizado' unless database.match?(/\Akanban_phase0_cw(4162|4180)_test\z/)
Rails.logger = ActiveSupport::Logger.new(File::NULL)
ActiveRecord::Base.logger = Rails.logger
ActiveJob::Base.logger = Rails.logger
ActiveJob::Base.queue_adapter = :test

def check(name)
  yield
  puts JSON.generate(check: name, status: 'pass')
rescue StandardError => error
  # Não imprimir corpo HTTP, mensagem de exceção ou headers: podem conter tokens.
  puts JSON.generate(check: name, status: 'fail', error_class: error.class.name)
  raise
end

def expect(value)
  raise 'Contrato divergente' unless value
end

def request(session, method, path, headers = {}, body = nil, status = 200)
  options = { headers: headers, as: :json }
  options[:params] = body unless body.nil?
  session.public_send(method, path, **options)
  if session.response.status != status
    error = session.request.env['action_dispatch.exception']
    puts JSON.generate(http_status: session.response.status, expected: status,
                       error_class: error&.class&.name, location: error&.backtrace&.first)
  end
  expect(session.response.status == status)
  JSON.parse(session.response.body) unless session.response.body.blank?
end

begin
  ActiveRecord::Base.transaction do
    account = Account.create!(name: 'Auditoria isolada', locale: 'pt_BR')
    other = Account.create!(name: 'Outra conta isolada', locale: 'pt_BR')
    account.enable_features!('api_and_webhooks')
    password = SecureRandom.hex(24) + 'aA1!'
    users = %w[administrator agent].map do |role|
      user = User.new(name: role, email: "#{SecureRandom.hex(8)}@example.test", password: password)
      user.skip_confirmation!
      user.save!
      AccountUser.create!(account: account, user: user, role: role)
      user
    end
    admin, agent = users
    inboxes = 2.times.map do |i|
      channel = Channel::Api.create!(account: account)
      Inbox.create!(account: account, channel: channel, name: "Caixa #{i}")
    end
    InboxMember.create!(inbox: inboxes.first, user: agent)
    sessions = users.map { ActionDispatch::Integration::Session.new(Rails.application) }
    credentials = []
    check('sessao_login_profile') do
      users.zip(sessions).each do |user, session|
        request(session, :post, '/auth/sign_in', {}, { email: user.email, password: password })
        headers = %w[access-token client uid].to_h { |key| [key, session.response.headers[key]] }
        expect(headers.values.all?(&:present?))
        credentials << headers
        profile = request(session, :get, '/api/v1/profile', headers)
        membership = profile.fetch('accounts').find { |a| a['id'] == account.id }
        expect(profile['id'] == user.id && membership['status'] == 'active')
        expect(membership['role'] == user.account_users.find_by!(account: account).role)
      end
      request(ActionDispatch::Integration::Session.new(Rails.application), :get, '/api/v1/profile', {}, nil, 401)
    end
    base = "/api/v1/accounts/#{account.id}"
    check('inboxes_agente_admin_isolamento') do
      visible = request(sessions.last, :get, "#{base}/inboxes", credentials.last).fetch('payload')
      expect(visible.map { |i| i['id'] } == [inboxes.first.id])
      all = request(sessions.first, :get, "#{base}/inboxes", credentials.first).fetch('payload')
      expect(all.map { |i| i['id'] }.sort == inboxes.map(&:id).sort)
      request(sessions.last, :get, "/api/v1/accounts/#{other.id}/inboxes", credentials.last, nil, 401)
      InboxMember.find_by!(inbox: inboxes.first, user: agent).destroy!
      expect(request(sessions.last, :get, "#{base}/inboxes", credentials.last).fetch('payload').empty?)
      InboxMember.create!(inbox: inboxes.first, user: agent)
    end
    service_headers = { 'api_access_token' => admin.access_token.token }
    check('atributos_modelos_tipos_unicidade_conta') do
      expect(request(sessions.first, :get, "#{base}/custom_attribute_definitions", service_headers).empty?)
      [1, 0].each do |model|
        body = { custom_attribute_definition: { attribute_key: 'kanban_etapa', attribute_display_name: 'Funil / Etapa',
                  attribute_display_type: 0, attribute_model: model, attribute_description: 'Contrato isolado' } }
        request(sessions.first, :post, "#{base}/custom_attribute_definitions", service_headers, body)
        request(sessions.first, :post, "#{base}/custom_attribute_definitions", service_headers, body, 422)
      end
      definitions = request(sessions.first, :get, "#{base}/custom_attribute_definitions", service_headers)
      expect(definitions.size == 2)
      expect(definitions.map { |d| d['attribute_model'] }.sort == %w[contact_attribute conversation_attribute])
      expect(definitions.all? { |d| d['attribute_display_type'] == 'text' })
      expect(other.custom_attribute_definitions.empty?)
    end
    contact = Contact.create!(account: account, name: 'Contato sintético', email: 'contact@example.test', contact_type: 'lead', custom_attributes: { kanban_etapa: 'Vendas / Novo' })
    ContactInbox.create!(contact: contact, inbox: inboxes.last, source_id: SecureRandom.uuid)
    check('contatos_agente_independente_caixa') do
      request(sessions.last, :get, "#{base}/contacts/#{contact.id}", credentials.last)
      visible = request(sessions.last, :get, "#{base}/contacts", credentials.last).fetch('payload')
      expect(visible.any? { |c| c['id'] == contact.id })
      request(sessions.last, :get, "/api/v1/accounts/#{other.id}/contacts/#{contact.id}", credentials.last, nil, 401)
    end
    contact_inbox = ContactInbox.create!(contact: contact, inbox: inboxes.first, source_id: SecureRandom.uuid)
    conversation = Conversation.create!(account: account, contact: contact, inbox: inboxes.first, contact_inbox: contact_inbox)
    # O identificador público é preenchido por trigger PostgreSQL.
    conversation.reload
    check('prioridade_nativa') do
      %w[low medium high urgent].each do |priority|
        request(sessions.first, :post, "#{base}/conversations/#{conversation.display_id}/toggle_priority", credentials.first,
                { priority: priority })
        expect(conversation.reload.priority == priority)
      end
    end
    check('automacao_condicao_atributo_contato') do
      rule = AutomationRule.create!(account: account, name: 'Condição isolada', event_name: 'conversation_created',
        conditions: [{ attribute_key: 'kanban_etapa', filter_operator: 'equal_to', values: ['Vendas / Novo'],
                       custom_attribute_type: 'contact_attribute', query_operator: nil }],
        actions: [{ action_name: 'add_label', action_params: ['fase0'] }])
      expect(AutomationRules::ConditionsFilterService.new(rule, conversation).perform)
      contact.update!(custom_attributes: { kanban_etapa: 'Vendas / Perdido' })
      expect(!AutomationRules::ConditionsFilterService.new(rule, conversation).perform)
    end
    check('webhook_api_secret_assinatura') do
      result = request(sessions.first, :post, "#{base}/webhooks", service_headers,
        { webhook: { name: 'Auditoria', url: 'https://example.test/kanban/events', subscriptions: ['contact_updated'] } })
      hook = result.fetch('payload').fetch('webhook')
      expect(hook['secret'].present?)
      payload = { event: 'contact_updated', account: { id: account.id }, id: contact.id }
      body = JSON.generate(payload)
      delivery = SecureRandom.uuid
      trigger = Webhooks::Trigger.new(hook['url'], payload, :account_webhook, secret: hook['secret'], delivery_id: delivery)
      headers = trigger.send(:request_headers, body)
      expected = 'sha256=' + OpenSSL::HMAC.hexdigest('SHA256', hook['secret'], "#{headers['X-Chatwoot-Timestamp']}.#{body}")
      expect(headers['X-Chatwoot-Signature'] == expected && headers['X-Chatwoot-Delivery'] == delivery)
      hooks = request(sessions.first, :get, "#{base}/webhooks", service_headers).fetch('payload').fetch('webhooks')
      expect(hooks.any? { |h| h['id'] == hook['id'] && h['secret'] == hook['secret'] })
    end
    check('dashboard_scripts_configuracao_controller') do
      marker = '<script data-kanban-phase0 src="/kanban/loader.js" defer></script>'
      config = InstallationConfig.find_or_initialize_by(name: 'DASHBOARD_SCRIPTS')
      config.value = marker
      config.save!
      GlobalConfig.clear_cache
      controller = DashboardController.new
      controller.request = ActionDispatch::TestRequest.create
      controller.request.path_info = "/app/accounts/#{account.id}/dashboard"
      controller.send(:set_dashboard_scripts)
      expect(controller.instance_variable_get(:@dashboard_scripts) == marker)
      controller.request.path_info = '/app/auth/password/edit'
      controller.send(:set_dashboard_scripts)
      expect(controller.instance_variable_get(:@dashboard_scripts).nil?)
    end
    check('usuario_servico_platform_api') do
      platform = PlatformApp.create!(name: 'Auditoria isolada')
      platform.platform_app_permissibles.create!(permissible: account)
      headers = { 'api_access_token' => platform.access_token.token }
      result = request(sessions.first, :post, '/platform/api/v1/users', headers,
        { name: 'kanban-bot', email: "#{SecureRandom.hex(8)}@example.test", password: SecureRandom.hex(24) + 'aA1!' })
      id = result.fetch('id')
      request(sessions.first, :post, "/platform/api/v1/accounts/#{account.id}/account_users", headers,
        { user_id: id, role: 'administrator' })
      token = request(sessions.first, :post, "/platform/api/v1/users/#{id}/token", headers).fetch('access_token')
      expect(User.find(id).account_users.pluck(:account_id) == [account.id])
      request(sessions.first, :get, "#{base}/custom_attribute_definitions", { 'api_access_token' => token })
      request(sessions.first, :post, "/platform/api/v1/accounts/#{other.id}/account_users", headers,
        { user_id: id, role: 'administrator' }, 401)
    end
    check('sessao_logout_revogacao') do
      request(sessions.last, :delete, '/auth/sign_out', credentials.last)
      request(sessions.last, :get, '/api/v1/profile', credentials.last, nil, 401)
    end
    raise ActiveRecord::Rollback
  end
rescue StandardError
  exit 1
ensure
  Current.reset
end
