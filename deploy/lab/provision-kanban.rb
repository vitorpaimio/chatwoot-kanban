# Exclusivo da stack descartável cwlab; saída sensível consumida por pipe em memória.
require 'json'
require 'securerandom'
account = Account.find(1)
User.transaction do
  ActiveRecord::Base.connection.execute('SELECT pg_advisory_xact_lock(741824)')
  manifest = InstallationConfig.find_or_initialize_by(name: 'KANBAN_LAB_MANIFEST')
  if manifest.persisted?
    state = JSON.parse(manifest.value)
    raise 'Manifesto incompatível' unless state.fetch('account_ids') == [1]
    user = User.find(state.fetch('service_user_id'))
    raise 'Associações inesperadas' unless user.account_users.pluck(:account_id) == [1]
  else
    email = 'kanban-cwlab@service.invalid'
    raise 'Usuário preexistente não pertence ao instalador' if User.exists?(email: email)
    password = SecureRandom.hex(48) + 'Aa1!'
    user = User.new(name: 'Serviço Kanban (laboratório)', email: email,
                    password: password, password_confirmation: password)
    user.skip_confirmation!
    user.save!
    AccountUser.create!(account: account, user: user, role: :administrator)
    state = { 'account_ids' => [1], 'service_user_id' => user.id,
              'service_user_ownership' => 'created' }
  end
  loader = '<script data-chatwoot-kanban src="/kanban/loader.js" defer></script>'
  config = InstallationConfig.find_or_initialize_by(name: 'DASHBOARD_SCRIPTS')
  unless config.value.to_s.include?('data-chatwoot-kanban')
    config.value = config.value.to_s + "\n" + loader
    config.save!
    state['loader_ownership'] = 'created'
  end
  state['loader_ownership'] ||= 'preexisting'
  manifest.value = JSON.generate(state)
  manifest.save!
  puts 'KANBAN_CREDENTIAL=' + JSON.generate({account: 1, token: user.access_token.token})
end
GlobalConfig.clear_cache
