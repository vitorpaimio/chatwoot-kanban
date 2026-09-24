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

A rede pública Swarm é resolvida pelo label explícito do Rails, pela configuração
de rede do provedor no Traefik (argumento ou variável de ambiente) ou pela única
rede comum comprovada. A rede deve pertencer a ambos os serviços; a rede do banco
não serve como fallback. Mais de um Traefik ou redes ambíguas bloqueiam a descoberta.
Configuração estática em arquivo não é interpretada; nesses casos, use um label
explícito do Rails quando a interseção de redes não for única. O preflight também
confere instalações persistidas e recusa divergência, sem reescrever o manifesto.
A precedência de label sobre rede padrão segue a
[documentação do provedor Swarm](https://doc.traefik.io/traefik/reference/install-configuration/providers/swarm/).

No Swarm, webhook usa a origem pública, preservando a proteção SSRF do Chatwoot.
O adaptador administrativo remove o webhook interno legado somente se o recibo
comprovar criação pela instalação e o ID/URL ainda corresponderem. Recursos
preexistentes ou modificados por terceiros são preservados. Compose mantém o
callback interno do seu contrato local; esta decisão não amplia sua certificação.

Antes de registrar recursos no Chatwoot, a instalação Swarm aguarda até 90 segundos
pela rota pública do loader, com timeout HTTP de 10 segundos, TLS verificado e sem
seguir redirecionamentos. Exige 200 e conteúdo igual ao loader desta versão para
recusar login, erro do proxy e arquivo obsoleto em cache. O status repete a prova;
saúde interna sozinha não implica funcionamento público. O loader criado pelo
instalador usa `async`, preservando DOMContentLoaded mesmo se a rota cair depois.
O teste de GET público não substitui prova de entrega de evento assinado pelo
Sidekiq; a validação de implantação deve confirmar um evento real processado.

No Swarm, a descoberta inclui aliases de `TaskTemplate.Networks` do serviço,
restritos ao ID da rede compartilhada com Rails. Isso cobre PostgreSQL em outra
stack cujo alias não aparece no inspect do container. Com `config.force_ssl`
ativo, `chatwoot_url` usa `FRONTEND_URL`, obrigatoriamente HTTPS; uma origem HTTP
interrompe a descoberta antes de criar recursos. Sem SSL forçado, a URL interna
permanece. O adaptador Compose não muda.

O caminho HTTPS depende de DNS, certificado e acesso ao proxy/CDN público a partir
dos containers. WAF, Access e limites de requisições precisam permitir a API do
Chatwoot; o instalador não contorna nem altera essas regras. Instalações já
persistidas não são redescobertas automaticamente. A recuperação de uma tentativa
falha está descrita no [guia avançado](../instalacao-avancada.md#recuperar-falha-de-ssl-no-swarm).

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
