# Ensaio opt-in no Rails local, sempre revertido e sem imprimir recibos/tokens.
raise 'Exige KANBAN_RESOURCE_PROBE=1' unless ENV['KANBAN_RESOURCE_PROBE'] == '1'
require 'stringio'
script = File.read(File.join(ENV.fetch('KANBAN_REPO'), 'installer/resources.rb'))
ActiveRecord::Base.transaction do
  registry = InstallationConfig.find_or_initialize_by(name: 'KANBAN_INSTALLER_V1')
  registry.value = { 'installations' => {}, 'loader_created' => true }.to_json
  registry.save!
  scripts = InstallationConfig.find_or_initialize_by(name: 'DASHBOARD_SCRIPTS')
  legacy_loader = '<script data-chatwoot-kanban src="/kanban/loader.js" defer></script>'
  scripts.value = '<script>/* preservado */</script>' + legacy_loader
  scripts.save!
  probe_accounts = 2.times.map { |i| Account.create!(name: "Ensaio reversível #{i}") }
  name = 'kanban-routing-probe'
  legacy = "http://#{name}_api:8000"
  preexisting = probe_accounts.last.webhooks.create!(
    url: "#{legacy}/kanban/webhooks/#{probe_accounts.last.id}/events",
    subscriptions: ['contact_created']
  )
  request = {
    'operation' => 'install', 'identity' => SecureRandom.uuid,
    'name' => name, 'accounts' => probe_accounts.map(&:id), 'attributes' => [],
    'callback' => legacy
  }
  run_adapter = lambda do
    original = $stdout
    begin
      $stdout = StringIO.new
      eval(script, binding)
    ensure
      $stdout = original
    end
  end
  run_adapter.call
  owned_legacy = probe_accounts.first.webhooks.find_by!(url: "#{legacy}/kanban/webhooks/#{probe_accounts.first.id}/events").id
  request['callback'] = 'https://kanban-probe.example.invalid'
  2.times { run_adapter.call }
  raise 'Webhook próprio antigo permaneceu' if Webhook.exists?(owned_legacy)
  raise 'Webhook preexistente removido' unless Webhook.exists?(preexisting.id)
  probe_accounts.each do |account|
    raise 'Webhook público duplicado/ausente' unless account.webhooks.where(url: "#{request['callback']}/kanban/webhooks/#{account.id}/events").count == 1
  end
  value = scripts.reload.value
  raise 'Loader ainda bloqueia DOMContentLoaded' if value.include?(legacy_loader)
  raise 'Loader async ausente' unless value.include?('src="/kanban/loader.js" async')
  request['operation'] = 'uninstall'
  run_adapter.call
  raise 'Script alheio alterado' unless scripts.reload.value == '<script>/* preservado */</script>'
  raise 'Webhook alheio removido no uninstall' unless Webhook.exists?(preexisting.id)
  raise ActiveRecord::Rollback
end
puts 'RESOURCE_PROBE_OK: migração, repetição, propriedade e loader; transação revertida'
