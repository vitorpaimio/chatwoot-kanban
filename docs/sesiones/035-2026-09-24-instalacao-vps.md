# Sessão 035 — Instalação no terminal da VPS

O mantenedor esclareceu o fluxo desejado: rodar um script e subir a integração com
poucas perguntas. Autorizou tornar público o repositório e confirmou separadamente
a abertura da imagem GHCR após bloqueio da revisão automática dessa segunda ação.
Ambos foram tornados públicos. A varredura dos 480 objetos históricos não encontrou
os padrões pesquisados de tokens GitHub/AWS ou chaves privadas; isso não é uma
auditoria exaustiva de segredos.

Implementados shell de entrada, imagem de ferramentas, descoberta administrativa,
seleção de conta e confirmação do plano, reutilizando backup e ciclo de vida.
Documentado `/opt/chatwoot-kanban`, incluindo mounts e chave. README simplificado;
procedimento manual movido para o guia avançado. CI acrescenta ensaio real no runner
antes de promover a imagem do instalador. Nenhum Docker reinstalado no Mac.

Ver [ADR-038](../adr/038-instalacao-vps.md) e os resultados do workflow do commit.
Os gates de certificação da release 0.2.0 permanecem separados desta entrega.

Validação local: Ruff, 164 testes Python (dois opt-in omitidos), quatro testes
JavaScript, sintaxe do shell e ajuda do CLI aprovados. Relatos privados habilitados
com confirmação adicional explícita do mantenedor.
