# Sessão 026 — Timeout provocado pelo cache de métricas

Relato: indicador amarelo, quadro vazio e timeout de 15 segundos.
Diagnóstico real no PostgreSQL: dez conexões da API ocupadas, transações ociosas
com escritas não confirmadas e UPSERT do cache bloqueado. O mutex assíncrono era
liberado antes do commit externo; requisições com múltiplas chaves formavam um
ciclo entre mutex Python e bloqueio PostgreSQL. Reinícios anteriores aliviavam
apenas o sintoma.

Correção em app/metrics/service.py: remover o mutex e coordenar escritores com
pg_try_advisory_xact_lock por conta/chave. Sem obter o lock, retornar os dados
consultados sem gravar cache; não aguardar a outra transação.

Validação: 78 testes Python em kanban_test, incluindo duas transações simultâneas
com chaves em ordem oposta e reutilização do cache; quatro testes Node; Ruff.
API reiniciada. Métricas reais concluíram no Chatwoot; consulta ao banco depois
mostrou seis conexões ociosas fora de transação e zero bloqueados. Retorno ao
Kanban conferido. Nenhuma alteração de schema, token ou fonte do Chatwoot.

Próximo passo: continuar a validação manual da Fase 1.
