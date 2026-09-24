# A seleção validada de contas é fornecida pelo adaptador via stdin.
require 'json'
result = {}
Account.transaction do
  ActiveRecord::Base.connection.execute('SET TRANSACTION READ ONLY')
  kanban_account_ids.each do |id|
    account = Account.find(id)
    result[id.to_s] = account.custom_attribute_definitions.map do |definition|
      definition.attributes.slice(
        'id', 'attribute_key', 'attribute_model',
        'attribute_display_type', 'attribute_values'
      )
    end
  end
end
puts 'KANBAN_INVENTORY=' + JSON.generate(result)
