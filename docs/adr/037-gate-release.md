# ADR-037 — Gate rastreável da release 0.2.0

Estado: aceito em 24/09/2026. Complementa ADR-023 e ADR-029.

## Contexto

As fases 2–4.2 foram implementadas e ensaiadas, mas a documentação pública ainda
as descrevia como futuras. O workflow publicava tags de branch e SHA sem registrar
uma referência por digest para o operador. Os ensaios dos instaladores cobrem
ARM64/CE 4.18.0, enquanto o build inclui também amd64.

## Decisão

Preservar a licença MIT, confirmada pelo mantenedor nesta sessão. Manter o gate
`publish.needs: test` e registrar o digest retornado pelo build no resumo e em
artefato do mesmo workflow. Acrescentar rótulos OCI de origem, revisão e licença.
Ampliar Ruff ao instalador/laboratórios e a sintaxe JS a todos os arquivos próprios.

Manter uma matriz explícita de evidências e um checklist de publicação. Versão
0.2.0, nova tag e release só entram no candidato final com gates satisfeitos;
a preparação documental não constitui publicação nem certificação de produção.
A publicação de imagens de branch segue o fluxo já vigente, sem criar releases.

## Consequências

Operadores poderão copiar uma referência imutável do build testado. CI não substitui
navegador real, ensaio por arquitetura, carga final ou instalação independente.
Os limites históricos ficam preservados e a documentação principal reflete o
estado atual. Nenhuma mudança no banco, nas APIs ou no código do Chatwoot.

## Ajuste operacional após autorização de envio

Em 24/09/2026, a consulta ao GitHub confirmou `master` como única branch remota e
padrão. O workflow passa a disparar também nela, preservando main/develop para o
fluxo documentado. Enviar para master publica imagem de branch após os testes;
não cria a release 0.2.0 nem altera a visibilidade privada do repositório.
O README passa a orientar instalação pelo mesmo commit e digest aprovados na CI,
com autenticação para acesso privado e pull no contexto Docker selecionado.
