# ADR-032 — Exclusão recuperável de negociações

Data: 23/09/2026. Estado: aceito.

## Decisão

A exclusão solicitada na validação manual remove apenas a negociação. A migração
008 registra a exclusão em kb_card_deletions, mantendo cartão, eventos, contato e
tarefa compartilhada. kb_authorized_cards mantém o escopo de autorização e
kb_visible_cards exclui registros removidos do quadro, relatórios e métricas.
A projeção dos atributos ignora negociações excluídas.

DELETE /cards/{id} e POST /cards/{id}/restore exigem versão atual, conta habilitada,
autorização por caixa/criador, bloqueio do contato, histórico e fila na mesma
transação. A interface oferece lixeira ao lado do X, confirmação e Desfazer após
excluir. O downgrade exige restaurar previamente todas as negociações excluídas;
não reintroduz dados silenciosamente.

## Ajustes relacionados de interface

Com conversa vinculada, mostrar apenas Abrir conversa; Vincular conversa aparece
somente sem vínculo. Concluir tarefa fica ao lado de Salvar com ícone de confirmação.
O filtro de etiquetas une catálogo da conta Chatwoot e etiquetas presentes nos
cartões; carregar somente os valores existentes nos cartões escondia o catálogo.

## Validação

Testes PostgreSQL verificam autorização, concorrência por versão, exclusão,
restauração, preservação da tarefa/contato/histórico e projeção sem cartão excluído.
Prova manual no Chatwoot local: nove cartões passaram a oito após exclusão e
voltaram a nove com Desfazer, preservando valores. Catálogo exibiu 123 e 1234;
rodapé da tarefa e ocultação do vínculo conferidos visualmente.
