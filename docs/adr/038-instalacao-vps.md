# ADR-038 — Instalação por comando na VPS

Estado: aceito em 24/09/2026.

## Contexto

O mantenedor pediu instalação pelo terminal da VPS com poucas perguntas, sem
preparar Python/JSON/digest manualmente, e autorizou abertura do repositório e,
separadamente, publicação da imagem GHCR.

## Decisão

`install.sh` executa uma imagem de instalador que inclui Python, Docker CLI e
Compose. Só aceita Linux/root/socket local. Usa host networking e monta apenas o
socket Docker e `/opt/chatwoot-kanban` no mesmo caminho, necessário aos bind mounts.
Acesso ao socket equivale a administração da VPS; a imagem vem do pacote do projeto.
O runtime fica fixado por digest na imagem de instalador do mesmo commit.

`installer.quickstart` inspeciona Rails/contas em transação de leitura, seleciona
banco pelas redes/aliases do host configurado no Rails e reaproveita o ciclo de vida
existente. Ambiguidade exige escolha; `--yes` confirma somente plano inequívoco.
Não instala um Chatwoot novo, não altera seu código nem adota bancos externos.
Swarm reutiliza labels Traefik do Rails. Compose mantém o contrato do gateway HTTP
próprio, com uma pergunta de URL, sem reconfigurar Nginx/TLS preexistentes.

Estado e trava duráveis permitem repetição/update/status/uninstall. Nenhum token é
pedido ao operador. O shell não baixa Python nem altera pacotes do host.
A CI publica o candidato por SHA e só promove a tag do instalador após ensaio
real de instalação repetida, sessão humana no navegador, webhook e remoção em
runner descartável. O laboratório do Mac não é reinstalado.

## Consequências

O caminho principal do README é um comando; o JSON fica no guia avançado. Abertura
de código e imagens permite baixar sem login, mantendo MIT e os limites de suporte.
Swarm sem labels inequívocas, réplicas múltiplas, banco externo, proxies arbitrários
e instalação do Chatwoot do zero não são adivinhados. O gate final da 0.2.0 continua
separado da disponibilização do instalador.
