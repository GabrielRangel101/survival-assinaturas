# Sobrevivência de assinantes — Gazeta Meridiano (projeto de portfólio)

> ⚠️ **Dados 100% sintéticos.** "Gazeta Meridiano" é um jornal digital fictício criado só para este
> projeto de portfólio. Nenhum dado, meta ou número de empresa real foi usado. Os efeitos foram
> **plantados de propósito**: o projeto mostra que o método recupera o efeito certo, não uma
> descoberta sobre o mundo.

Análise de sobrevivência aplicada à retenção de assinaturas: quanto tempo cada tipo de assinante
permanece, onde a retenção quebra e qual canal vale a verba quando se considera **permanência** e não
só custo de aquisição.

> Todo número deste arquivo é gerado a partir de [`results/results.json`](results/results.json)
> (`python run_all.py`); nada é digitado à mão. Um teste confere isso.

## Resumo executivo

**Retenção medida (Kaplan-Meier, não "ativos ÷ iniciados").** Em M12, 66,1%
(IC 95% 65,1% a 67,1%), acima da
meta fictícia de 65%. Em M18, 51,0%
(IC 49,7% a 52,3%), abaixo da meta de 55%.
**M24 não é observável**: com entradas até o corte de 31/10/2026, ninguém tem 24 meses completos
(0 assinantes), então a célula fica vazia em vez de preenchida com um número inventado.

**Onde a retenção quebra.** No mês seguinte ao fim da promoção da Black Friday (60% de desconto por
3 meses), 10,3% de quem chegou ao mês 3 cancela em apenas um mês, contra
3,6% de quem entrou sem promoção. O Cox ajustado estima um risco
**2,85×** maior nesse mês (IC 95% 2,26 a 3,61); o Cox ingênuo, com um HR único para a
promoção, enxerga só 1,20× e **subestima o penhasco**.

**Qual canal vale a verba.** Mídia paga (Meta) é o canal pago mais barato por assinante
(R$ 52), mas a permanência inverte o ranking: o LTV descontado em
24 meses de Indicação é R$ 498 contra
R$ 369 de Mídia paga (Meta), e o retorno por real investido é de
8,9× contra 7,1×. **Busca paga** é o pior retorno entre os
canais com verba (4,4×).

**Decisão (projeção sobre premissas explícitas, não medição).**
Mover R$ 100.000 de Busca paga para Indicação adiciona
cerca de R$ 444,3 mil de valor líquido (LTV − CAC), supondo que o CAC médio valha
na margem. No mês 3 da promoção, uma ação de retenção de R$ 4 por assinante
tratado rende R$ 2.565 líquidos por coorte de referência (efetividade assumida de
35%) e só se paga se evitar mais de
16% do excesso de cancelamentos.

## O que este projeto demonstra

- **A. Desenho**: evento (cancelamento efetivo), origem do tempo (primeira cobrança), corte fixo e censura à direita.
- **B. O erro clássico**: retenção ingênua por safra × Kaplan-Meier com IC 95% (log-log); metas editáveis; sem
  preencher M12/M18/M24 onde a safra não tem tempo de observação.
- **C. Comparações**: log-rank por canal, plano e safra; pares com correção de Holm.
- **D. Cox**: razões de risco com IC e C-index; teste de riscos proporcionais (Schoenfeld) que **mostra a violação**;
  correção (estratificação por plano + promoção por períodos + reajuste); tabela plantado × estimado.
- **E. Valor por canal**: RMST e LTV descontado em 24 meses × CAC, payback e IC por bootstrap de
  assinantes, separando **medido** de **projetado**.
- **F. O que poderia ter dado errado**: censura ignorada, riscos proporcionais violados, ranking por M12 bruto com safra pequena.
- **G. Riscos competitivos**: incidência acumulada voluntário × involuntário × fim de contrato (Aalen-Johansen).
- **H. Limites honestos** (abaixo).

## Resultados

### A. Desenho

| Item | Valor |
|---|---|
| Assinantes sintéticos | 12.000 (seed 42) |
| Entradas | 01/11/2024 a 31/10/2026 |
| Corte de observação | 31/10/2026 |
| Cancelaram (evento) | 3.945 (32,9%) |
| Censurados à direita (ainda ativos) | 8.055 (67,1%) |
| Seguimento máximo possível | 24,0 meses |
| Assinantes com ≥ 12 / ≥ 18 / ≥ 24 meses possíveis | 5.296 / 2.857 / 0 |

Causas observadas: voluntário 3.057, involuntário (falha de pagamento) 626,
fim de contrato 262.

### B. Ingênuo × Kaplan-Meier por safra

A "retenção ingênua" (ativos ÷ iniciados) só mede **há quanto tempo a safra entrou**: ela vai de
45% (S1) a 94% (S8)
e correlaciona −1,00 (Spearman) com a idade da safra. O KM em M3, comparável entre safras,
conta a história oposta (correlação +0,93: as safras recentes retêm um pouco **pior**).

| Safra | Entrada | n | Ingênua | KM M3 | KM M6 | KM M12 | KM M18 | KM M24 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| S1 | Nov/24–Jan/25 | 1.679 | 45% | 90,4% | 81,1% | 67,8% ▲ | 52,2% ▼ | — | 
| S2 | Fev/25–Abr/25 | 1.153 | 52% | 89,3% | 81,4% | 68,3% ▲ | 54,3% | — | 
| S3 | Mai/25–Jul/25 | 1.265 | 55% | 89,5% | 82,5% | 69,3% ▲ | — | — | 
| S4 | Ago/25–Out/25 | 1.199 | 60% | 88,1% | 80,7% | 67,4% | — | — | 
| S5 | Nov/25–Jan/26 | 2.019 | 65% | 88,4% | 77,5% | — | — | — | 
| S6 | Fev/26–Abr/26 | 1.215 | 73% | 87,1% | 77,3% | — | — | — | 
| S7 | Mai/26–Jul/26 | 1.689 | 82% | 85,3% | — | — | — | — | 
| S8 | Ago/26–Out/26 | 1.781 | 94% | — | — | — | — | — | 

"—" = safra sem tempo de observação (não preenchida). ▲/▼ = IC 95% inteiro acima/abaixo da meta fictícia
(M12 65%, M18 55%, M24 48%; editáveis em `src/sobrevivencia/config.py`).

### C. Comparações (log-rank, Holm)

| Fator | χ² (gl) | p | Pares significativos (bruto → Holm) |
|---|---:|---:|---:|
| Canal | 341,4 (5) | < 0,001 | 15 → 15 de 15 |
| Plano | 285,9 (3) | < 0,001 | 6 → 6 de 6 |
| Safra | 37,8 (7) | < 0,001 | 12 → 5 de 28 |

Retenção KM em M12 por canal: Orgânico 71,0%; Busca paga 64,7%; Mídia paga (Meta) 55,9%; Social 56,9%; Indicação 81,1%; E-mail/CRM 75,0%.

### D. Cox: plantado × estimado

O modelo **ingênuo** (riscos proporcionais, um HR por covariável) viola a premissa: o teste de Schoenfeld rejeita
4 de 13 covariáveis (global p < 0,001). O modelo **corrigido**
(estratificado por plano, promoção por períodos, reajuste como efeito de calendário) não é rejeitado
(global p 0,949). C-index: 0,652 (ingênuo) e 0,623
(corrigido, só compara assinantes do mesmo plano).

| Efeito | Plantado | Cox ingênuo (IC 95%) | Cox corrigido (IC 95%) |
|---|---:|---:|---:|
| Canal: busca paga (vs orgânico) | 1,15 | 1,18 (1,07–1,29) | 1,17 (1,07–1,29) |
| Canal: mídia paga Meta (vs orgânico) | 1,50 | 1,48 (1,35–1,61) | 1,49 (1,36–1,62) |
| Canal: social (vs orgânico) | 1,20 | 1,34 (1,20–1,49) | 1,33 (1,19–1,48) |
| Canal: indicação (vs orgânico) | 0,70 | 0,71 (0,60–0,83) | 0,72 (0,61–0,84) |
| Canal: e-mail/CRM (vs orgânico) | 0,85 | 0,90 (0,80–1,01) | 0,90 (0,80–1,02) |
| Engajamento (+1 desvio-padrão) | 0,78 | 0,79 (0,77–0,82) | 0,79 (0,77–0,82) |
| Entrou pelo Passe Copa | 1,60 | 1,90 (1,58–2,30) | 1,48 (1,22–1,79) |
| Dispositivo: desktop (vs mobile) | 1,00 | 1,03 (0,96–1,10) | 1,03 (0,96–1,11) |
| Dispositivo: tablet (vs mobile) | 1,00 | 1,03 (0,92–1,16) | 1,02 (0,91–1,15) |
| Plano: combo (vs mensal) | 0,75 | 0,78 (0,72–0,85) | 0,79 (0,72–0,85)¹ |
| Plano: estudante (vs mensal) | 1,20 | 1,11 (1,03–1,21) | 1,19 (1,09–1,29)¹ |
| Plano: anual (vs mensal) | — | 0,45 (0,40–0,51) | — |
| Entrou na Black Friday (efeito único) | — | 1,20 (1,09–1,31) | — |
| Promoção vigente (meses 0–3) | 0,85 | — | 0,91 (0,76–1,08) |
| Penhasco (mês 3–4, 1º mês a preço cheio) | 3,00 | — | 2,85 (2,26–3,61) |
| Pós-penhasco (meses 4–6) | 1,35 | — | 1,48 (1,18–1,86) |
| Reajuste de preço (Mensal/Combo, jul–ago/26) | 1,50 | — | 1,61 (1,46–1,78) |

¹ HR de plano estimado num modelo complementar sem o plano anual (que é estratificado no modelo corrigido).
Cobertura dos IC 95% sobre os efeitos plantados: 100% no corrigido (13 efeitos) contra
91% no ingênuo.

**Validação em 20 réplicas** (seeds diferentes, mesmo gerador): o maior viés relativo médio entre os efeitos foi de
3,8% e os IC 95% cobriram o valor plantado em 97% dos
260 intervalos, ou seja, o resultado acima não depende da seed oficial.

### E. Valor por canal (RMST, LTV descontado, CAC, payback)

| Canal | CAC (premissa) | RMST 24m (meses) | LTV 24m (R$) | % medido | LTV/CAC | Payback (mensalidades) |
|---|---:|---:|---:|---:|---:|---:|
| Orgânico * | R$ 30 | 16,9 (16,5–17,2) | R$ 454 (R$ 445–R$ 465) | 100% | 15,1× (14,8–15,5) | 2 |
| Busca paga | R$ 95 | 15,6 (15,2–16,1) | R$ 423 (R$ 411–R$ 435) | 100% | 4,4× (4,3–4,6) | 4 |
| Mídia paga (Meta) | R$ 52 | 13,4 (13,0–13,8) | R$ 369 (R$ 357–R$ 380) | 100% | 7,1× (6,9–7,3) | 2 |
| Social | R$ 60 | 14,4 (13,8–15,0) | R$ 377 (R$ 362–R$ 392) | 98% | 6,3× (6,0–6,5) | 3 |
| Indicação | R$ 56 | 19,0 (18,4–19,7) | R$ 498 (R$ 479–R$ 518) | 100% | 8,9× (8,5–9,2) | 3 |
| E-mail/CRM * | R$ 22 | 17,9 (17,4–18,4) | R$ 494 (R$ 479–R$ 509) | 100% | 22,5× (21,8–23,2) | 1 |

\* canal próprio, de capacidade limitada: não entra na realocação de verba. IC 95% por bootstrap de assinantes
(1.000 réplicas). **Medido** = parte do LTV coberta por Kaplan-Meier com pelo menos
30 assinantes sob risco; o resto é projeção de cauda com risco constante. ARPU, CAC e taxa de desconto
(12% ao ano) são **premissas**.

### F. O que poderia ter dado errado

1. **Censura ignorada**: na retenção M12 de toda a base (verdade plantada 65,4%), tratar censurado como
   cancelado dá 30%, descartar os censurados dá
   54%; o KM dá 66,1%.
2. **Riscos proporcionais violados**: o HR único da promoção (1,20) prevê
   4,3% de cancelamento no mês 3–4, mas o observado é
   10,3% (10,0% no modelo corrigido).
3. **Ranking por M12 bruto com safra pequena**: com 300 assinantes, o ranking bruto acerta o
   melhor canal em 66% dos 1.000 sorteios e o pior em
   51%.

### G. Riscos competitivos (Aalen-Johansen)

Até M18: voluntário 36,9%, involuntário 7,1%,
fim de contrato (só anual) 5,0%. "1 − KM tratando as outras causas como censura"
superestima o voluntário (39,4% contra 36,9% corretos).

## Limites honestos

- **Dados sintéticos e efeitos plantados.** O projeto mostra que o método recupera o efeito certo (tabela D), não que
  mídia paga seja pior ou que a Black Friday tenha um penhasco no mundo real.
- **M24 não é observável** com este desenho de janela; qualquer número de M24 seria projeção.
- **Premissas de valor**: ARPU = preço de tabela por plano (sem reajuste), CAC por canal, taxa de desconto, custo e efetividade da ação do mês 3
  são premissas minhas, em `src/sobrevivencia/config.py` e listadas em [`DECISIONS.md`](DECISIONS.md). Não apliquei margem de contribuição.
- **CAC médio ≠ CAC marginal**: a realocação de verba supõe escala linear; canais como indicação saturam.
- O KM assume censura não informativa; como há efeitos de calendário (reajuste, Copa), o KM agregado mistura safras com riscos diferentes.
- **Não foi feito**: modelos de fragilidade/cura, múltiplas reativações, upgrade de plano, efeito causal do reajuste (só associação),
  validação temporal fora da amostra.

## Como rodar

Requer Python 3.11–3.13 com wheels (em Python 3.15 as bibliotecas científicas ainda podem não ter wheels; veja `DECISIONS.md`).
Sem Makefile: comandos para PowerShell (Windows).

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run_all.py
.\.venv\Scripts\python.exe -m pytest
```

Linux/macOS: troque `.\.venv\Scripts\python.exe` por `./.venv/bin/python`. `run_all.py` gera os dados (`data/`), a verdade plantada
(`results/ground_truth.json`), todos os resultados (`results/results.json`), as figuras (`reports/figures/`), o relatório HTML
(`report/`), os documentos (este README, `DECISIONS.md`, `portfolio/`) e executa os notebooks. Opções: `--rapido` (menos réplicas de bootstrap),
`--sem-notebooks`, `--sem-gate`.

## Relatório interativo

[`report/sobrevivencia-assinaturas.html`](report/sobrevivencia-assinaturas.html) é um arquivo único, sem CDN e sem servidor (HTML + CSS + JavaScript puro, figuras
embutidas, modo noturno) com um **explorador**: escolha canal, plano, safra e horizonte (M12/M18/M24), veja a curva com IC e edite a linha de meta.

## Estrutura

```
├── README.md · DECISIONS.md · LICENSE · requirements.txt · pyproject.toml
├── run_all.py                    # gera dados, análises, figuras, results.json e documentos
├── src/sobrevivencia/            # pacote: config, simulate, km, cohorts, cox, value, pitfalls, competing, ...
├── templates/                    # modelos (README, DECISIONS, relatório, case): números só via placeholders
├── results/                      # results.json (fonte única) e ground_truth.json (verdade plantada)
├── reports/figures/              # PNGs
├── report/                       # relatório HTML autônomo
├── notebooks/                    # 01 exploração · 02 análise (executados)
├── portfolio/                    # case.md, texto do card e HTML pronto para public/demos/
├── tests/                        # pytest
└── .github/workflows/ci.yml      # CI: pytest
```

## Stack

Python 3.13.17, pandas 2.3.3, NumPy 2.5.5, SciPy 1.18.1,
lifelines 0.30.3, statsmodels 0.15.0, Matplotlib 3.11.2,
Jupyter, pytest. Reprodutível com a seed 42.

## Feito com apoio de IA, sob minha direção

Este projeto foi construído por mim, Gabriel Rangel, **com apoio de IA (Claude), sob minha direção**: eu defini a pergunta de negócio, o desenho do
estudo, as premissas e os critérios de aceite; a IA escreveu e testou o código a partir dessas instruções. Os dados são sintéticos e os resultados
não representam nenhuma empresa real.

Licença: MIT.
