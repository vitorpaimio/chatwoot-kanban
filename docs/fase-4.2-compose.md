# Fase 4.2 — Compose/Nginx

**Concluída no ambiente certificado:** Compose 5.5.1, Docker Engine 29.5.2,
Chatwoot CE 4.18.0, Nginx 1.28.3, ARM64 e HTTP.

O adaptador usa o mesmo provisionamento, backup cifrado, manifesto e revogação da
fase 4. Consulte [ADR-036](adr/036-instalador-compose-nginx.md).

## Configuração

Copie `deploy/installer.compose.example.json` e substitua imagem por digest real,
contas, contexto, projeto/serviços Compose e redes existentes. O exemplo não é uma
imagem publicável. `chatwoot_service` e `chatwoot_database_service` são as chaves
Compose (`rails`, `postgres`), não nomes completos de containers. `chatwoot_url`
precisa usar o alias Rails na rede externa selecionada. Só uma réplica local por
serviço é suportada. O banco Chatwoot precisa permitir `pg_dump` pelo usuário
configurado dentro do container; use `rails_wrapper` se o Rails depende de um
wrapper para carregar segredos externos.

`listen_host` é `127.0.0.1` por padrão; `listen_port` deve corresponder à porta de
`public_url` e estar livre. O Nginx criado encaminha a mesma origem para ambos os
aplicativos. Ajuste a origem pública do Chatwoot conforme sua instalação. O
instalador não reescreve configuração do Nginx anterior. HTTPS/TLS externo e
contextos Docker remotos não fazem parte desta certificação.

O diretório de estado precisa ser acessível ao daemon para bind mounts. No Mac,
compartilhe esse caminho com a VM Docker. Os arquivos privados `mounts/` são
necessários enquanto o projeto roda; não mova ou apague o estado. Contêm senha do
banco e chave de cifragem em claro com acesso restrito, **não** o token Chatwoot.
Backup e cofre são cifrados; guarde também `recovery.key` para restauração.

## Operação

Exemplo com a rede `chatwoot_default`:

```sh
python -m installer install --config compose.json --dry-run \
  --confirm-network chatwoot_default
python -m installer install --config compose.json \
  --confirm-network chatwoot_default
python -m installer status --config compose.json
python -m installer update --config compose.json \
  --confirm-network chatwoot_default
python -m installer restore --config compose.json \
  --confirm-network chatwoot_default --backup backup-DATA.fernet
python -m installer uninstall --config compose.json \
  --confirm-network chatwoot_default
```

O diretório padrão é `.local/installations/<name>`; use `--state-dir` para outro
caminho e mantenha-o em todas as operações. Apenas a imagem pode mudar entre
instalação e atualização. Execute `status` após restore; restore não reverte os
recursos compartilhados do Chatwoot. Não execute atualizações do Chatwoot em
paralelo com este instalador.

Uninstall preserva volume, backups e atributos. Para remover somente os atributos
criados e ainda correspondentes ao recibo, adicione `--purge-attributes
--confirm-attribute-data-loss`. Isso pode apagar valores de contatos. O gateway
Nginx desta instalação também é removido; a configuração/acesso anteriores ao
Chatwoot não são alterados. Reinstalar com o mesmo estado reutiliza o volume.

## Ensaio reproduzível

Roteiro destrutivo opt-in em `tests/contracts/phase42_compose.py`, restrito a
`colima-kanban-phase42` e ao projeto `cwcompose`. O script
`deploy/compose-lab/prepare.py` gera a infraestrutura descartável a partir da
imagem Chatwoot oficial fixada no laboratório anterior. Requer Docker Compose,
Python do projeto, PyYAML e, para navegador, Playwright e Chrome local.

```sh
colima start kanban-phase42 --cpu 4 --memory 6 --disk 40 --vm-type vz \
  --mount /CAMINHO/ABSOLUTO/chatwoot-kanban:w --mount-type virtiofs
docker --context colima-kanban-phase42 build -t kanban-lab:phase42 .
PHASE42_DISPOSABLE=colima-kanban-phase42 PYTHONPATH=. \
  .venv/bin/python deploy/compose-lab/prepare.py
PHASE42_DISPOSABLE=colima-kanban-phase42 PYTHONPATH=. \
  .venv/bin/python tests/contracts/phase42_compose.py
```

As credenciais humanas sintéticas passam por memória/stdin; não há storageState
persistido. O relatório público é `docs/phase42-evidence.json`. A exclusão final
do laboratório elimina bancos, backups e chaves locais; o relatório permanece.

Evidências: [ensaio real](phase42-evidence.json) e [sessão 032](sesiones/032-2026-09-24-fase-4.2-compose.md).

O laboratório desta sessão e as ferramentas Docker foram removidos após o ensaio.
Os comandos acima recriam um ambiente novo; os backups e URLs do ensaio não estão mais ativos.
