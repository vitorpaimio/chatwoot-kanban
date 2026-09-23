# Convenções de Python

## Análise de código

O Ruff usa as regras de `ruff.toml` e a configuração do projeto em
`pyproject.toml`:

- `E`, `F`: erros de estilo e de código.
- `I`: ordenação de importações.
- `N`: convenções de nomes.
- `UP`: modernização da sintaxe.
- `B`: erros comuns detectados pelo Bugbear.
- `SIM`: simplificações.
- `ARG`: argumentos não utilizados.
- `RUF100`: supressões `noqa` desnecessárias.

```bash
ruff check . && ruff format --check .
```

## Formatação

- Limite de 88 caracteres por linha.
- Recuo de quatro espaços e aspas duplas.
- Sem espaços no fim das linhas.
- Quebra de linha ao final do arquivo.

## Tipagem

Todas as funções públicas devem ter anotações de parâmetros e retorno.
Use `| None` em vez de `Optional[T]`; prefira `Sequence` e `Mapping` nas
interfaces que não precisam de coleções mutáveis. `self` e `cls` dispensam
anotação explícita. Ruff não substitui um verificador de tipos.

## Importações

Ordene primeiro a biblioteca padrão, depois dependências e, por último,
módulos locais, separando os grupos com uma linha em branco:

```python
import asyncio
from collections.abc import Sequence

import httpx

from app.config import settings
```

Ruff pode ordenar as importações automaticamente. Textos e docstrings usam
pt-BR; identificadores técnicos existentes são preservados por compatibilidade.
