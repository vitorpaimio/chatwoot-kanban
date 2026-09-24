# Sessão 036 — PR de instalação do cliente

Revisado o PR #1, baseado no relato de instalação Chatwoot 4.17.1 em Swarm
de nó único x86_64, Traefik e PostgreSQL em stack separada. O alias do banco
estava somente no serviço; HTTP interno era redirecionado pelo SSL do Rails.
Preservadas as duas correções do autor e acrescentada recusa de `FRONTEND_URL`
HTTP quando SSL é obrigatório. O teste novo falhou no código original do PR
e passou após o ajuste. ADR-038 e guia de recuperação atualizados.

Validação local: 170 testes Python passaram no PostgreSQL exclusivo `kanban_test`,
dois opt-in omitidos; Ruff, formatação dos dois arquivos Python alterados,
sintaxe JavaScript e quatro testes JavaScript aprovados. No Chatwoot real local,
um processo Rails isolado com `force_ssl=true` retornou 301 para HTTP e 401 para
HTTPS sem credenciais, confirmando redirecionamento e chegada à autenticação,
sem alterar código nem dados do Chatwoot.

Limites: Docker ausente neste ambiente; instalação completa com Swarm, TLS,
ativação e proxy público continua pendente. O ensaio Rails local não certifica
essa topologia nem substitui validação na instalação do cliente.
A execução de CI do PR está em `action_required`; a revisão automática de
permissões bloqueou sua liberação por exigir autorização para executar código
externo. Não houve merge nem publicação da imagem corrigida.
