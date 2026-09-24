# Política de segurança

## Relato privado

Não publique credenciais, dados pessoais ou detalhes exploráveis em issues públicas.
O canal escolhido é [GitHub Private Vulnerability Reporting](https://github.com/vitorpaimio/chatwoot-kanban/security/advisories/new).

Repositório público e Private Vulnerability Reporting habilitado em 24/09/2026.
Não há prazo de resposta prometido.

## Estado de suporte

A 0.2.0 está em preparação. Não há certificação de instalação pública em produção.
Os alvos de compatibilidade são Chatwoot Community Edition 4.16.2 e 4.18.0.
Consulte o [plano](docs/plano-0.2.0.md) e as
[matriz de compatibilidade](docs/compatibilidade-0.2.0.md) para distinguir testes de
contrato, testes de navegador e certificação de implantação.

## Controles implementados

- `app/security.py:identity` valida access-token/client/uid em `/api/v1/profile`,
  por headers ou cookie `cw_d_session_info`, e exige associação ativa à conta.
  Escritas verificam Origin quando presente e recusam Sec-Fetch-Site cross-site.
- Configuração administrativa exige papel de administrador. Referências compostas
  e consultas por conta protegem a associação de cartões, contatos e etapas.
- Tokens técnicos e segredos de webhook são cifrados com Fernet no banco Kanban.
  `ENCRYPTION_KEY` é obrigatória e deve ficar protegida, fora dos backups do banco.
- `workspace.webhook` exige HMAC-SHA256 de timestamp.corpo, janela de tempo,
  correspondência da conta e ID de entrega. Não há modo de assinatura opcional.
- `database.record` grava histórico e fila `kb_sync` na transação. O worker tenta
  novamente o envio do estado mais recente. SSE revalida a sessão periodicamente.
- Mensagens entre frames validam origem, emissor, conta e identificador. A interface
  usa APIs DOM de texto e valida URLs de imagens. CSV protege células de fórmulas.
- O serviço usa usuário sem privilégios na imagem. As páginas só permitem iframe
  da mesma origem e a especificação OpenAPI não está exposta.

## Limitações atuais

- Cartões, movimentos, histórico e métricas usam a caixa da conversa vinculada.
  Agentes consultam `/inboxes` com a própria sessão; cache de 60 segundos, com
  falha fechada. Revogação pode levar até 60s. Cards sem conversa são visíveis ao
  administrador e criador. Contatos/tarefas seguem a política CE de contatos da conta.
  Esta política não equivale às permissões Enterprise ou a todos os acessos por time.
- Conta desativada bloqueia dados, eventos recebidos e unidades do worker. A operação
  aguarda unidades já em execução; depois da confirmação, nenhuma nova inicia.
- O token administrativo usado pelo worker tem alcance superior ao de um agente.
  Nunca o use para descobrir as permissões da sessão humana.
- Etapa/tarefa têm autoridade local; divergência observada reenfileira o espelho.
  A reconciliação periódica recupera eventos perdidos, com limites por conta.
- `/health` verifica banco, atraso da fila e heartbeat do worker; retorna 503
  quando degradado ou indisponível. O worker tem sonda própria por container.
- Não há autenticação por Cloudflare Access/JWT implementada ou necessária ao
  contrato de sessão atual. Um cabeçalho de e-mail de proxy não autentica ninguém.
- Os manifests atuais não implementam todos os controles de endurecimento de
  containers desejáveis. Não presumir filesystem read-only/capabilities removidas.
- Os instaladores foram ensaiados em Swarm e Compose ARM64 com CE 4.18.0.
  A publicação depende do gate final. Compose foi validado em HTTP local, sem
  certificação de TLS público. Consulte os limites na matriz de compatibilidade.

## Operação e desenvolvimento

Use HTTPS, banco privado, backup antes de alterações e conta técnica limitada às
contas escolhidas. Não registre tokens, cookies, senhas ou corpos sensíveis.
Não salve storageState de navegador ou sessões em arquivos temporários, capturas,
traces ou relatórios. Testes de navegador recebem credenciais pelo ambiente e
mantêm sessões em memória. Testes de indisponibilidade só podem usar ambiente isolado.

Não envie `.env`, dumps, chaves, arquivos de sessão ou dados reais em relatos.
Em caso de exposição, revogue a credencial no Chatwoot, substitua-a no Kanban e
avalie os dados acessíveis durante a janela. Backups e a chave Fernet exigem acesso
restrito. Consulte [backup e recuperação](docs/backup-recuperacao.md).
