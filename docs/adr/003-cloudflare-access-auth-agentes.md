# ADR-003 — Cloudflare Access como autenticação dos agentes

- **Data:** 2026-07-09
- **Estado:** Aceito

## Contexto

A aplicação deve ser acessível pela rede pública, mas apenas por agentes
autorizados. O cenário original era uma equipe com menos de dez pessoas,
com e-mail `@example.com` hospedado na Hostinger, sem Google Workspace ou
Microsoft 365.

Foram avaliados login próprio, OAuth do Google e Cloudflare Access com
código temporário enviado por e-mail.

## Decisão

Adotar Cloudflare Access, com acesso restrito aos e-mails corporativos e
código de uso único. A validação do JWT no servidor faz parte da arquitetura
planejada; **ainda não está implementada nesta cópia**.

## Fundamentação técnica

O cabeçalho `Cf-Access-Jwt-Assertion` transporta o JWT assinado. A aplicação
deve verificar assinatura, emissor, audiência e validade usando as chaves
publicadas em `https://{team}.cloudflareaccess.com/cdn-cgi/access/certs`.

`Cf-Access-Authenticated-User-Email` informa o e-mail, mas não é, sozinho,
uma prova criptográfica de identidade. Não se deve confiar nesse cabeçalho
quando a origem puder ser acessada fora da proteção do Access.

A revogação de acesso acontece na política do Cloudflare. As chaves públicas
precisam de cache e atualização para acompanhar sua rotação.

## Consequências

- A tabela `agentes` não precisa de senha nem sessão própria: associa e-mail,
  nome e, opcionalmente, `chatwoot_agent_id`.
- O Access não define papéis dentro da aplicação. No MVP, todos os agentes
  têm os mesmos direitos; permissões diferentes exigiriam lógica própria.
- `CF_ACCESS_TEAM_DOMAIN` e `CF_ACCESS_AUD` foram reservados para a integração.

## Alternativas descartadas

Login próprio exigiria recuperação de senha e gestão de sessões. Contas
Google pessoais misturariam identidades pessoais e corporativas e
prejudicariam a revogação centralizada. Uma URL sem autenticação exporia
informações de contatos.

## Nota da auditoria de 2026-09-23

O código atual lê o e-mail informado no cabeçalho e usa o bot na sua ausência.
Isso não equivale à validação JWT planejada neste ADR.

## Exemplos técnicos registrados

```sql
CREATE TABLE agentes (
  id                SERIAL PRIMARY KEY,
  email             TEXT NOT NULL UNIQUE,   -- origem: cabeçalho do Cloudflare Access
  nombre            TEXT NOT NULL,
  chatwoot_agent_id INTEGER,                -- vínculo opcional com o agente no Chatwoot
  activo            BOOLEAN NOT NULL DEFAULT true
);
```
