# Demonstração visual em português do Brasil

As cinco capturas deste diretório foram regeneradas em 23/09/2026 a partir
dos modelos HTML atuais, com respostas de API simuladas no navegador.
Mostram quatro etapas, oito contatos fictícios e dois agentes nos temas
claro e escuro. Nenhum dado real ou token foi utilizado.

| Captura | Conteúdo |
|---------|----------|
| [kanban-light.png](kanban-light.png) | Quadro no tema claro |
| [kanban-dark.png](kanban-dark.png) | Quadro no tema escuro |
| [kanban-task-modal.png](kanban-task-modal.png) | Modal de edição de tarefa |
| [dashboard-light.png](dashboard-light.png) | Painel de agentes no tema claro |
| [dashboard-dark.png](dashboard-dark.png) | Painel de agentes no tema escuro |

Essas capturas verificam a apresentação; não comprovam sincronização com
Chatwoot nem persistência no PostgreSQL.

## Demonstração completa descrita no histórico

O [ADR-018](../adr/018-demo-mockup-chatwoot.md) registrou ferramentas locais
que não foram publicadas: `demo/mock_chatwoot.py`, `demo/seed_db.py`,
`demo/screenshot.py` e `docker-compose.demo.yml`. Elas estão no `.gitignore`
e não existem nesta cópia.

Naquele ambiente, o servidor simulado fornecia definições de atributos,
filtros, leitura e atualização de contatos e avatares SVG. As datas eram
relativas ao dia atual. PostgreSQL escutava na porta 5433, a API simulada
na 8095 e a aplicação na 8000. O serviço `db-seed` preenchia agentes e auditoria.

Se essas ferramentas forem recuperadas e revisadas, os comandos históricos eram:

```bash
docker compose -f docker-compose.demo.yml up -d --build
python demo/screenshot.py
```

A geração de capturas exigia Playwright e Chromium. Os contatos simulados
viviam em memória, perdendo alterações ao reiniciar. A versão de API Docker
1.44 foi uma particularidade da máquina usada na sessão original, não uma
configuração necessária para todos os ambientes.

Para validar a versão presente, siga o [guia de contribuição](../../CONTRIBUTING.md)
e o alcance descrito na [auditoria](../auditoria-2026-09-23.md).
