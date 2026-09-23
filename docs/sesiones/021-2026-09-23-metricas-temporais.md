# Sessão 021 — Métricas completas do Pipeline

- Tela em `/kanban/metricas`, dentro do menu Pipeline, com oito blocos, filtros na
  URL, gráficos locais, comparativos e exportação CSV.
- Eventos/dimensões adicionados via migrações 004/005 após backup em
  `.local/antes-metricas-004.dump`; dados existentes preservados.
- Oito contatos locais tiveram seus metadados atualizados sem movimentar cartões.
- Motivos configuráveis por conta; modal obrigatório para perda, inclusive Outro.
- Configuração de negociações paradas por funil, padrão sete dias.
- Testes: 35 Python com PostgreSQL real; três JavaScript; Ruff e checagem sintática
  de metricas.js, kanban.js e loader.js aprovados.
- Navegador real: período vazio retorna 0%/sem dados; filtros Hoje + John + Acme
  Support retornam uma negociação. Perda do contato de teste 1790186608874 via modal
  registrada como “Outro: Validação local das métricas”, etapa de saída Novo; ranking
  e resumo atualizados. Card de teste permanece em Perdido como evidência local.
- Tema claro/escuro conferidos no Chatwoot, com capturas em `docs/evidencias/metricas`.
- Limitação explícita: saldos atuais de atendimento não possuem histórico na API
  nativa. Tempos não existentes e dimensões legadas desconhecidas não são inventados.
- Serviços locais continuam em execução; nenhuma implantação remota realizada.
- Responsividade conferida em 768 px e 390 px. Corrigido reposicionamento após a
  transição do sidebar nativo; no celular, largura de conteúdo e viewport do iframe
  iguais a 375 px, sem transbordamento horizontal. Tamanho original e tema claro
  restaurados. Console do navegador sem erros na verificação final.
