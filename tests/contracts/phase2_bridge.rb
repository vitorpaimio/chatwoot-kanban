# Ponte em memória: o provisionador Python exercita controllers Rails reais.
require 'json'
require 'securerandom'
abort 'Exige Rails test CE' unless Rails.env.test? && !ChatwootApp.enterprise?
database = ActiveRecord::Base.connection_db_config.database
abort 'Banco não autorizado' unless database.match?(/\Akanban_phase0_cw(4162|4180)_test\z/)
Rails.logger = ActiveSupport::Logger.new(File::NULL)
ActiveRecord::Base.logger = Rails.logger
ActiveJob::Base.logger = Rails.logger
ActiveJob::Base.queue_adapter = :test
$stdout.sync = true
ActiveRecord::Base.transaction do
  account = Account.create!(name: 'Fase 2 isolada', locale: 'pt_BR')
  account.enable_features!('api_and_webhooks')
  user = User.new(name: 'Serviço isolado', email: "#{SecureRandom.hex(12)}@example.test",
                  password: SecureRandom.hex(24) + 'aA1!')
  user.skip_confirmation!
  user.save!
  AccountUser.create!(account: account, user: user, role: :administrator)
  token = user.access_token.token
  contact = Contact.create!(account: account, name: 'Contato isolado', email: 'fase2@example.test', contact_type: 'lead',
                            custom_attributes: { origem: 'Feira', alheio: 'preservar' })
  session = ActionDispatch::Integration::Session.new(Rails.application)
  puts JSON.generate(account: account.id, contact: contact.id)
  while (line = $stdin.gets)
    command = JSON.parse(line)
    break if command['stop']
    params = command['json'] || command['params'] || {}
    session.public_send(command.fetch('method').downcase,
      "/api/v1/accounts/#{account.id}#{command.fetch('path')}",
      headers: { 'api_access_token' => token }, params: params, as: :json)
    body = session.response.body.blank? ? {} : JSON.parse(session.response.body)
    puts JSON.generate(status: session.response.status, body: body)
  end
  raise ActiveRecord::Rollback
end
