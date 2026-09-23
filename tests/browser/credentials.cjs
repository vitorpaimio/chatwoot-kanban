"use strict";

const email = process.env.CHATWOOT_LOGIN_EMAIL;
const password = process.env.CHATWOOT_LOGIN_PASSWORD;
if (!email || !password) {
  throw new Error(
    "Configure CHATWOOT_LOGIN_EMAIL e CHATWOOT_LOGIN_PASSWORD. Use somente uma conta local de testes.",
  );
}

module.exports = { email, password };
