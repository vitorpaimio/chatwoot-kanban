abort 'Execute somente no desenvolvimento local' unless Rails.env.development?
config = InstallationConfig.find_by(name: 'DASHBOARD_SCRIPTS')
if config
  config.value = config.value.to_s.gsub(/\s*<script data-chatwoot-kanban src="\/kanban\/loader.js" defer><\/script>/, '')
  config.save!
end
origin = ENV.fetch('KANBAN_PUBLIC_URL', 'http://localhost:3000')
Webhook.where('url LIKE ?', "#{origin}/kanban/webhooks/%").destroy_all
DashboardApp.where(title: 'Kanban').find_each do |app|
  app.destroy! if app.content.any? { |item| item['url'].to_s.start_with?("#{origin}/kanban/") }
end
GlobalConfig.clear_cache
puts 'Loader e integrações locais removidos. Dados do Kanban preservados.'
