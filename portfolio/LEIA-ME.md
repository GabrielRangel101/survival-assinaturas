# Pasta portfolio/

Material pronto para o case entrar na seção **Estatística aplicada** do portfólio
(<https://gabriel-rangel.vercel.app/projetos>), ao lado de "Teste A/B e Impacto: Assinaturas".
Nada aqui altera o repositório do site: é só o que você precisa copiar.

| Arquivo | Para quê |
|---|---|
| `case.md` | Texto do case, no formato dos cases do site (Problema, Decisão, O que a análise mostra, Destaques, Tecnologias utilizadas, Meu papel, Como foi feito, Limites). Os metadados (slug, categoria, tipo de dado, período, stack) ficam no cabeçalho. |
| `card.txt` | Texto do card na listagem de projetos (até 250 caracteres). |
| `metadata.json` | Slug `sobrevivencia-assinaturas`, categoria `Estatística aplicada`, tecnologias do card, caminho do HTML e link do repositório. |
| `public/demos/sobrevivencia-assinaturas.html` | Relatório HTML autônomo (sem CDN), pronto para ir em `public/demos/` do site. É cópia exata de `report/sobrevivencia-assinaturas.html`. |

## Passos sugeridos (no repositório do site)

1. Copie `public/demos/sobrevivencia-assinaturas.html` para `public/demos/` do site.
2. Cadastre o case com o slug `sobrevivencia-assinaturas` e a categoria **Estatística aplicada**, usando `card.txt` como descrição do card e `case.md` como corpo.
3. Aponte o botão de código para `https://github.com/GabrielRangel101/survival-assinaturas` (depois de publicar o repositório) e o de demonstração para `/demos/sobrevivencia-assinaturas.html`.

Todos os números de `case.md`, `card.txt` e do HTML vêm de `results/results.json`; para regenerar tudo, rode `python run_all.py` na raiz do projeto.
