# Matriz de compatibilidade — preparação da 0.2.0

Atualizada em 24/09/2026. Evidências descrevem os ensaios registrados; não são
certificação de qualquer instalação de produção nem do futuro commit da release.

| Ambiente | Evidência disponível | Limite / gate restante |
| --- | --- | --- |
| Chatwoot CE 4.16.2 | Contratos Rails, 10 grupos | Navegador integrado e instaladores no candidato final pendentes |
| Chatwoot CE 4.18.0 | Contratos Rails, navegador autenticado, webhook e ciclo de vida dos dois adaptadores | Revalidar o candidato final e instalação por terceiro |
| Swarm ARM64, nó único, Traefik 3.7.13 | Duas instalações, repetição, worker, update, falha/restore e uninstall | Não certifica HA, múltiplos nós ou amd64 |
| Compose local ARM64, Engine 29.5.2, Compose 5.5.1, Nginx 1.28.3 | HTTP, sessão humana, isolamento, webhook, update, falha/restore e uninstall | TLS público, daemon remoto e alteração de Nginx existente não certificados |
| linux/amd64 | Plataforma configurada no build da CI | Execução operacional ainda não certificada |
| Capacidade local | 20.000 contatos, 5.000 cartões/conta, 30 sessões mistas durante cinco minutos | Ensaio ASGI/PostgreSQL não certifica proxy, navegador ou hardware da implantação final |
| Aplicativo móvel nativo | Ausência do menu Pipeline documentada | Integração móvel não suportada nesta release |

Fontes: [contratos](fase-0-contratos-0.2.0.md),
[autorização](fase-1-autorizacao.md), [capacidade](fase-3-quadro-capacidade.md),
[Swarm](fase-4-instalador.md), [Compose](fase-4.2-compose.md),
[evidência Swarm](phase4-evidence.json) e [evidência Compose](phase42-evidence.json).
Os laboratórios Docker anteriores foram removidos; seus relatórios permanecem.

## Escolha do adaptador

Use Swarm/Traefik quando o Chatwoot já estiver em Swarm e houver rede compartilhada
confirmada. Use Compose/Nginx quando o Chatwoot já estiver em Compose local e for
possível encaminhar a origem por um gateway Nginx próprio em porta explícita.
Ambos preservam a imagem e o código do Chatwoot. O Compose não edita o proxy
preexistente. Consulte os requisitos e a proteção do diretório de estado nos guias.

Use `imagem@sha256:...` obtida da execução da CI que testou o commit escolhido.
Tags de branch são mutáveis. Uma imagem multiarch disponível não prova o
funcionamento em todas as arquiteturas; os gates da release estão na
[Fase 5](fase-5-release.md).
