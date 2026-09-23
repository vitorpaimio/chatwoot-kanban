# ADR-029 — Contratos e plano da release 0.2.0

Data: 23/09/2026. Estado: aceito como direção; implementação por fases.

## Contexto

A auditoria encontrou lacunas entre integração local atual e distribuição pública.
O mantenedor definiu acesso de agentes por caixa, autoridade local de etapa/tarefa,
criação manual e instalador com usuário técnico dedicado por contas selecionadas.

## Decisão

Adotar o [plano 0.2.0](../plano-0.2.0.md). Agentes terão acesso somente a cartões
cuja conversa vinculada esteja nas caixas retornadas com sua sessão; administradores
veem a conta. A conversa segue atividade mais recente, salvo fixação explícita.
Tarefa continua compartilhada por contato/conta, inicialmente atribuída ao criador.

Provisionar atributos por conta na Fase 2 com catálogo único, compatibilidade de
modelo/tipo, mapeamento de opcionais e manifesto de propriedade. Não apagar atributos
preexistentes. Novas chaves portuguesas exigem migração aditiva dos espelhos antigos.

Priorizar Swarm/Traefik, rede configurável network_public, seguido de Compose/Nginx.
Instalador usa User normal administrador nas contas escolhidas e token cifrado;
plano explícito e revogação no uninstall. Primeira release pública será nova tag
0.2.0, com Brasília/BRL e meta de 20 mil contatos, 5 mil cartões e 30 usuários.
A1 é o primeiro item posterior à release.

## Consequências e validação

Os [contratos](../fase-0-contratos-0.2.0.md) passaram em Rails CE 4.16.2 e 4.18.0
isolados. Isso valida o mecanismo de caixas e permite planejar agentes, mas não
substitui implementação de G5 nem certificação no navegador. Cache, tarefas entre
escopos, licença, canal privado e acesso móvel têm decisões pendentes no plano.
Mudanças de saúde da fila/worker ficam nas Fases 2/4. Nenhuma dessas funcionalidades
futuras foi implementada na Fase 0; os ADRs atuais continuam descrevendo o executável
até a substituição explícita dos respectivos comportamentos.
