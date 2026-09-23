# Convenções de comentários

## Princípio geral

O código deve ser autoexplicativo. Comentários existem quando o código não
consegue expressar o motivo de uma decisão. Use português do Brasil.

## Docstrings

Use docstrings em módulos e funções públicos quando a finalidade não for
óbvia. Adote o estilo Google, preservando os marcadores reconhecidos pelas
ferramentas:

```python
"""Busca conversas filtradas por um atributo personalizado.

Args:
    attribute_key: Chave do atributo usado no filtro.
    value: Valor procurado.

Returns:
    Resposta JSON original da API do Chatwoot.
"""
```

- Métodos privados (`_`) só precisam de docstring quando a lógica não for trivial.
- Testes dispensam docstring quando seus nomes forem descritivos.
- Use uma linha quando for suficiente: `"""Retorna o nome completo do usuário."""`.

## Comentários pontuais

Explique apenas motivos não evidentes:

```python
# O Chatwoot rejeita conexões sem este cabeçalho específico.
headers["X-Special"] = "value"
```

Não use comentários para repetir o que o código faz, separar seções
artificialmente ou guardar código desativado; remova código sem uso.
