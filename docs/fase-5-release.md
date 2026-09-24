# Fase 5 — gate e publicação da 0.2.0

Estado: iniciada em 24/09/2026, sem publicação. MIT confirmada pelo mantenedor.
O pacote permanece em 0.1.0 até a preparação do candidato final; não reutilizar
uma tag antiga. Consulte o [ADR-037](adr/037-gate-release.md).

## Preparação implementada

- CI mantém publicação de imagens de branch dependente dos testes do mesmo commit.
- Ruff inclui instalador e scripts de laboratório. Sintaxe de todos os JavaScripts
  próprios e roteiros de navegador é verificada; testes Node continuam obrigatórios.
- Publicação registra `imagem@sha256:...` no resumo e no artefato
  `image-digest-<commit>`, com revisão, origem e licença MIT nos rótulos OCI.
- README, CHANGELOG e SECURITY refletem as fases implementadas e seus limites.
- [Matriz de compatibilidade](compatibilidade-0.2.0.md) distingue contratos,
  navegador, implantação e carga. Build multiarch não certifica execução.

O workflow publica imagens de master/main/develop após push aprovado pela CI.
Master é a branch padrão verificada no GitHub nesta sessão.
Ele não cria tag de versão nem GitHub Release. As alterações desta sessão ainda
precisam ser executadas no GitHub para produzir um digest; nenhum digest foi inventado.

## Critérios para liberar a publicação

| Gate | Situação | Prova exigida |
| --- | --- | --- |
| Licença | Resolvido | MIT confirmada em 24/09/2026; manter atribuições e licença do Chart.js |
| Validação local | Executada nesta sessão | Ruff, PostgreSQL exclusivo, sintaxe JS e testes Node; ver sessão 033 |
| Commit final na CI | Pendente | SHA definido e execução verde de Ruff, migrações, pytest e JavaScript |
| Imagem por digest | Preparado na CI; execução pendente | Referência imutável do build do mesmo SHA aprovado |
| Navegador CE 4.16.2 e 4.18.0 | Pendente no candidato final | Sessão, autorização/isolamento, quadro, tarefas, métricas e SSE contra Chatwoot real |
| Swarm e Compose | Ensaios prévios disponíveis | Reexecução com a imagem candidata e registro de versão, arquitetura e digest |
| Arquiteturas publicadas | ARM64 ensaiada; amd64 pendente | Ciclo de vida e integração real em cada arquitetura anunciada |
| Backup/restauração | Ensaiados nas fases 4 e 4.2 | Repetir no candidato final, preservar dados e provar saúde após falha |
| Capacidade final | Pendente | Metas e hardware registrados; 20.000 contatos, 5.000 cartões e 30 sessões mistas |
| Instalação por terceiro | Pendente | Outra pessoa executa o guia em ambiente suportado e registra resultado sem credenciais |
| Canal privado | Habilitado em 24/09/2026 | Private Vulnerability Reporting ativo; envio de relato não ensaiado |
| Abertura do repositório | Resolvido em 24/09/2026 | Repositório e imagem públicos por autorização do mantenedor |
| Versão e release nova | Pendente | Atualizar versão para 0.2.0, changelog datado, tag nova e release com digest e matriz |

## Sequência para concluir

1. Definir ambiente final, hardware, operador terceiro e arquiteturas a publicar.
   A CI atual constrói ARM64 e amd64; reduzir o escopo exige decisão explícita e
   atualização da matriz, sem apresentar uma arquitetura não ensaiada como suportada.
2. Preparar o candidato com versão 0.2.0 e changelog revisado. Integrar as mudanças
   acumuladas em um commit identificável e executar a CI. Não usar o HEAD atual como
   identidade das alterações ainda não commitadas.
3. Instalar pelo digest emitido pela CI e executar os roteiros reais dos guias de
   Swarm/Compose, navegador nas duas versões, restauração e carga final. Registrar
   SHA, digest, versões, hardware e resultados, sem tokens ou dados pessoais.
4. Obter o relato da instalação independente e resolver o canal privado. Se houver
   correção de código, gerar novo candidato e repetir as verificações afetadas.
5. Após todos os gates e a aprovação manual prevista no fluxo do projeto, publicar
   a nova tag/release e documentar os digests, requisitos, limites e recuperação.

## Limites desta etapa

A preparação não recriou os laboratórios removidos nem executou uma instalação
por terceiro. Os relatórios anteriores não identificam o futuro commit da release.
Na preparação inicial não houve envio. O envio posterior foi autorizado e está
registrado na [sessão 034](sesiones/034-2026-09-24-envio-instalador.md).
Mudança de visibilidade, tag e release continuam fora deste envio.
