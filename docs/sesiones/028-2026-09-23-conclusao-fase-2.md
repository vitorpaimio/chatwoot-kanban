# Sessão 028 — Conclusão da Fase 2

Pedido: continuar até concluir a fase. Alterações locais anteriores preservadas;
sem alteração dos fontes do Chatwoot, commit ou publicação.

Entregue: manifesto persistente, configuração de atributos opcionais, diagnósticos,
importação separada com estimativa/modos/checkpoints, reconciliação periódica,
backoff por conta, processamento limitado, health de API/fila e heartbeat de worker.
Interface administrativa conectada ao fluxo. Migrações Alembic 009–011.

A revisão encontrou risco de inversão de locks ao atualizar o resumo da conta na
transação do contato. Recibo `kb_import_seen` é confirmado com contato/histórico/fila;
resumo é recomposto depois. Testes cobrem interrupção nesse intervalo e requisição
concorrente esperando o mesmo contato. Criação de cartão importado registra ID no
histórico, preservando a autorização de negociações múltiplas da Fase 1.

Validação: 107 testes Python, quatro Node, Ruff, sintaxe JS/CJS, dois roteiros de
navegador controlado e integração Python/Rails real CE 4.16.2 e 4.18.0 aprovados.
Migrações locais preservaram contagens; API e worker reiniciados, sondas 200 e fila
sem atraso. Conferidos quadro, configuração e manifesto na sessão real local;
provisionamento executado na conta 1, distinguindo criações e preexistentes.

Resultados, procedimentos e limites em
[relatório da Fase 2](../fase-2-provisionamento-recuperacao.md) e
[ADR-033](../adr/033-catalogo-atributos.md).

Próxima fase: Fase 3, quadro/métricas/capacidade. Hardware e metas de latência devem
ser definidos antes do ensaio. Validação manual histórica da Fase 1 e gates finais
não são declarados integralmente concluídos por estes testes.
