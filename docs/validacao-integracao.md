# Validação da integração — 23/09/2026

## Resultado local

Chatwoot **4.16.2**, Ruby **3.4.4**, PostgreSQL **16**, Redis, Vite e serviços
Kanban funcionando em **http://localhost:3000**. A interface é aberta pelo menu
interno após login. O código do repositório Chatwoot permanece sem alterações
(`git status --short` vazio). Não foi repetido seed e não houve implantação remota.

## Evidências executadas

| Verificação | Resultado |
|---|---|
| Python + PostgreSQL real | **20 testes passaram** |
| Ruff: app, migrações, scripts e testes | **Passou** |
| JavaScript: valores, datas, contratos de navegação | **3 testes passaram** |
| Sintaxe do JavaScript da interface e loader | **Passou** |
| Login e menu no Chatwoot real | **Passou** |
| Duas sessões, SSE e preservação de rascunho aberto | **Passou** |
| Vários funis, tarefa compartilhada, conclusão e recriação | **Passou** |
| Limpeza real da mensagem/vencimento no Chatwoot | **Passou** |
| Texto com HTML malicioso exibido como texto | **Passou** |
| Abrir conversa pelo cartão e Dashboard App compacta | **Passou** |
| Troca de conta, menu único, recolhimento, resize e Escape | **Passou** |
| Arrastar cartão no navegador real | **Passou** |
| Recusar postMessage de janela emissora incorreta | **Passou** |
| Reimportação real sem duplicação | **Passou** |
| API original com cabeçalho api_access_token pelo proxy | **HTTP 200** |
| Histórico, relatórios e SSE sem sessão | **HTTP 401** |
| Outra conta não autorizada | **HTTP 403** |
| Rails indisponível por 60 segundos | **Falhas persistidas e retomada validada** |
| Reinício do worker e movimentos consecutivos | **Estado mais recente sincronizado** |
| Reinício completo dos serviços, dados preservados | **Passou** |

Os testes PostgreSQL incluem concorrência, versões, rebalanceamento de posições,
referências entre contas, permissões, assinaturas, deduplicação, limpeza externa,
conflitos, sessão expirada/suspensa, SSE isolado e importação legada real com dump.
A cópia legada foi repetida sem duplicação, preservou as tabelas de origem e
recusou associações ambíguas. A importação respeita o bloqueio de arquivamento de etapas.

O teste de indisponibilidade registrou 4 tentativas após 20 segundos e 5 após 40/60
segundos. Após reiniciar, o worker enviou a tarefa atualizada e a última etapa,
sem recuperar projeções antigas. Os serviços foram restaurados ao final.

## Reproduzir

- `tests/browser/live.cjs`: fluxos completos com duas sessões reais.
- `tests/browser/drag.cjs`: arrastar cartão e validar janela emissora.
- `tests/browser/outage.py`: **interrompe o Rails local por 60 segundos**;
  exige a instalação local e supervisor configurados. Não pertence à suíte comum.
- `.local/kanban-duas-sessoes.png` e `.local/compact-real.png`: capturas locais
  da instalação real. Não são substitutos dos testes executados.

Os testes de navegador criam contatos e funis identificados como teste. O contato
original `jane` foi preservado. Os exemplos ficam disponíveis para experimentar a interface.

## Limites da entrega

A stack Swarm/Traefik e a publicação multiarch estão preparadas, mas **não foram
executadas em Docker/Swarm nesta máquina**. A CI foi configurada para bloquear
publicação sem testes do mesmo commit; nenhum push, build remoto ou deploy foi feito.
Os períodos anteriores à importação não são estimados nos relatórios.

Instalação e comandos: [guia local](instalacao-local.md).
Backup e migração: [recuperação](backup-recuperacao.md).
