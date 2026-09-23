# Política de segurança

## Relato privado

Não publique credenciais, dados pessoais ou detalhes exploráveis em issues públicas.
O canal privado oficial da release 0.2.0 ainda depende de decisão do mantenedor:
GitHub Private Vulnerability Reporting/Security Advisories ou e-mail dedicado.
Não há endereço de e-mail nem prazo de resposta confirmado nesta cópia.
Antes da publicação, o canal escolhido deve ser habilitado, testado e vinculado aqui.
Se a opção de relato privado não estiver disponível, solicite ao mantenedor um canal
privado sem divulgar a vulnerabilidade publicamente.

## Estado de suporte

A 0.2.0 está em preparação. Não há certificação de instalação pública em produção.
Os alvos de compatibilidade são Chatwoot Community Edition 4.16.2 e 4.18.0.
Consulte o [plano](docs/plano-0.2.0.md) e as
[evidências da Fase 0](docs/fase-0-contratos-0.2.0.md) para distinguir testes de
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

- Associação à conta ainda não restringe o Kanban por caixa/time. Não disponibilize
  esta versão a agentes que não possam ver todos os dados importados da conta.
  G5 e sua validação são gate da release, não um controle já implementado.
- O token administrativo usado pelo worker tem alcance superior ao de um agente.
  Nunca o use para descobrir as permissões da sessão humana.
- A reconciliação periódica de eventos perdidos e a autoridade exclusivamente local
  ainda serão implementadas. Hoje atributos externos podem alterar etapa/tarefa.
- `/health` atual só indica processo ativo. Verificação de banco/fila, heartbeat
  do worker e healthchecks dos manifests pertencem às Fases 2 e 4.
- Não há autenticação por Cloudflare Access/JWT implementada ou necessária ao
  contrato de sessão atual. Um cabeçalho de e-mail de proxy não autentica ninguém.
- Os manifests atuais não implementam todos os controles de endurecimento de
  containers desejáveis. Não presumir filesystem read-only/capabilities removidas.
- Não há instalador público certificado. Scripts Ruby locais só aceitam Rails em
  desenvolvimento e não substituem backup completo ou plano de recuperação.

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
