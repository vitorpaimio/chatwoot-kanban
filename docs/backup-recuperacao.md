# Backup e recuperação

Faça backups do banco Kanban, do banco Chatwoot e da chave `ENCRYPTION_KEY`.
Guarde a chave separadamente, com acesso restrito. Sem ela, tokens cifrados não podem ser recuperados.

```sh
umask 077
pg_dump -Fc -d kanban_development -f kanban.dump
pg_dump -Fc -d chatwoot_dev -f chatwoot.dump
```

Antes da instalação desta máquina, foi criado `.local/chatwoot-antes-kanban.dump`
e o backup dos scripts/configuração `.local/chatwoot-config-backup.json`.
O código anterior à integração está em `/tmp/kanban-antes-integracao.tar.gz`;
transfira-o para armazenamento durável se precisar conservar essa versão.

Para recuperar, pare API e worker, restaure o dump em um **novo banco**, configure
`DATABASE_URL` para esse banco, recupere a mesma chave e execute `alembic upgrade head`.
Valide contagens, tarefas e histórico antes de apontar os serviços. A fila persistida
retoma os trabalhos; o bloqueio transacional é liberado ao encerrar um worker.
Nunca sobreponha um banco ativo sem um backup adicional e autorização explícita.

## Dados do esquema antigo

As migrações Alembic só acrescentam tabelas `kb_*`. `agentes`, `tareas`,
`task_audit_log` e `webhook_events` não são removidas ou modificadas.
O importador exige conta de origem explícita e um backup PostgreSQL válido:

```sh
python -m scripts.import_legacy --account 1 --backup /caminho/kanban-legado.dump
python -m scripts.import_legacy --account 1 --backup /caminho/kanban-legado.dump --apply
```

Pare os escritores antigos antes de importar. Ative/importe os contatos da conta
no novo Kanban primeiro. A primeira execução valida; `--apply` copia tarefas e
histórico em uma transação e registra os IDs importados. Repetições não duplicam os registros.

O importador recusa tarefas sem contato/vencimento, agentes sem ID e e-mail
compatíveis com a conta e contatos que já tenham uma tarefa ativa concorrente.
Resolva essas associações explicitamente; não há associação automática ao usuário de serviço.
As tabelas de origem continuam disponíveis para comparação e recuperação.
