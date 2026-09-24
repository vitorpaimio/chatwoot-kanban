# Sessão 034 — Envio e guia de instalação

## Autorização e escopo

O mantenedor autorizou subir as alterações e exigiu que o README ensine outra
pessoa a instalar. A consulta ao GitHub confirmou repositório privado e `master`
como única branch remota/padrão. O envio inclui o trabalho acumulado das fases
anteriores e a preparação da Fase 5; não cria uma release certificada 0.2.0.

## Alterações

- README com requisitos, escolha Swarm/Compose, clone autenticado, Python,
  obtenção do commit/digest da CI, login/pull GHCR, configuração por campo, plano,
  instalação, verificação de saúde, primeiro acesso, atualização e remoção.
- Caminho Compose limitado a HTTP local, com acesso por túnel quando necessário;
  preservação do estado, mounts, chave e backups explicitada.
- CI inclui master nos gatilhos de PR/push. Sem isso, o envio à branch existente
  não executaria os testes nem publicaria a imagem ensinada no README.
- ADR-037 e gate da Fase 5 atualizados com a branch real e o escopo deste envio.

## Validação e envio

Ruff, sintaxe JavaScript, quatro testes Node e ajuda do CLI aprovados. Pytest
executado contra PostgreSQL exclusivo. Os ensaios de integração dos adaptadores
permanecem os das fases 4/4.2; Docker não foi reinstalado nesta sessão.
A imagem por digest depende da conclusão do workflow remoto deste envio.
Os gates de certificação final permanecem documentados na Fase 5.
