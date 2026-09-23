require 'json'
require 'fileutils'
abort 'Execute somente no desenvolvimento local' unless Rails.env.development?
script = '<script data-chatwoot-kanban src="/kanban/loader.js" defer></script>'
config = InstallationConfig.find_or_initialize_by(name: 'DASHBOARD_SCRIPTS')
existing = config.value.to_s
backup = ENV.fetch('KANBAN_CONFIG_BACKUP')
unless File.exist?(backup)
  File.write(backup, JSON.generate({ dashboard_scripts: existing, locales: Account.pluck(:id, :locale) }), mode: 'w', perm: 0600)
end
config.value = existing.include?('data-chatwoot-kanban') ? existing : existing + "\n" + script
config.save!
Account.find_each do |account|
  account.enable_features!('api_and_webhooks')
  account.update!(locale: 'pt_BR')
end
GlobalConfig.clear_cache
puts "Loader instalado e contas configuradas em português."
