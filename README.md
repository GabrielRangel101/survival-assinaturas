# Sobrevivência de assinantes — Gazeta Meridiano (projeto de portfólio)

> ⚠️ **Dados 100% sintéticos.** "Gazeta Meridiano" é um jornal digital fictício criado só para este
> projeto de portfólio. Nenhum dado, meta ou número de empresa real foi usado. Os efeitos foram
> **plantados de propósito**: o projeto mostra que o método recupera o efeito certo, não uma
> descoberta sobre o mundo. Para testar o método em dados que eu **não** plantei, o projeto roda o mesmo pipeline num
> dataset público de churn (seção J), e valida o modelo fora do tempo (seção I) e com geradores diferentes (seção J).

**Relatório interativo (sem instalar nada):**
[no portfólio](https://gabriel-rangel.vercel.app/projetos/sobrevivencia-assinaturas) ·
[página do relatório](https://gabrielrangel101.github.io/survival-assinaturas/) ·
[`report/sobrevivencia-assinaturas.html`](report/sobrevivencia-assinaturas.html) (arquivo único, abre offline).

Análise de sobrevivência aplicada à retenção de assinaturas: quanto tempo cada tipo de assinante
permanece, onde a retenção quebra e qual canal vale a verba quando se considera **permanência** e não
só custo de aquisição.

> Todo número deste arquivo é gerado a partir de [`results/results.json`](results/results.json)
> (`python run_all.py`); nada é digitado à mão. Um teste confere isso.

## Resumo executivo: 3 achados e 1 decisão

Intervalos são IC 95%. O que depende de premissa (CAC, margem, efetividade da ação) vem marcado como **projeção**.

**1. A retenção medida é 66,0% em M12 e 44,1% em M24.**
Por Kaplan-Meier (e não "ativos ÷ iniciados"): M12 66,0% (IC 65,2% a 66,8%),
acima da meta fictícia de 65%; M18 51,6%
(IC 50,7% a 52,5%), abaixo da meta de 55%;
M24 44,1% (IC 43,2% a 45,1%), abaixo da meta de 48%.
A conta ingênua por safra vai de 39% a 95% e tem correlação −0,98 com a idade da safra:
mede quando a safra entrou, não se ela retém.

**2. A retenção quebra no mês seguinte ao fim da promoção.** 10,5% de quem chegou ao mês 3 da Black Friday cancela em um mês,
contra 3,9% de quem entrou sem promoção. O Cox ajustado estima risco **2,64×** maior (IC 2,18 a 3,19);
o Cox ingênuo, com um HR único, enxerga só 1,14× e esconde o penhasco.

**3. O canal mais barato não é o que mais rende, mas o ranking de retorno depende de uma premissa (o CAC).**
Mídia paga (Meta) tem o menor CAC entre os canais com verba (R$ 52), mas a permanência põe Indicação na frente:
LTV de contribuição em 24 meses de R$ 357 (IC R$ 347 a R$ 367) contra
R$ 270 (IC R$ 263 a R$ 277). O ranking só por permanência não usa o CAC:
Indicação > Busca paga > Social > Mídia paga (Meta). 
Com o CAC variando 30% para cima e para baixo, o retorno por real é de 6,4× em Indicação
(IC 4,9 a 8,9) e 5,2× em Mídia paga (Meta)
(IC 4,1 a 7,3); Indicação é o melhor em 71% das réplicas.
Não é certeza: é uma vantagem moderada que some se o CAC de Mídia paga (Meta) cair 19% (R$ 42).

**Decisão (projeção, não medição).** Mover verba de Busca paga para Indicação **em etapas**, enquanto o CAC marginal de Indicação ficar abaixo de
96% acima do médio (ponto de equilíbrio; IC 23% a 208%).
Para cada R$ 100 mil movidos, o valor líquido é de R$ 312,2 mil (IC R$ 95,4 mil a R$ 581,7 mil) se o CAC marginal for igual ao médio
e de R$ 99,7 mil (IC −R$ 76,8 mil a R$ 290,2 mil) se for 50% maior. A ação de retenção no mês 3 só se paga se evitar mais de
22% do excesso de cancelamentos, e **não deve ser escalada antes de um teste**: provar 35% de efetividade exige
cerca de 2.671 assinantes por braço, mais do que uma campanha de Black Friday inteira (587 chegam ao mês 3).

## O que este projeto demonstra

- **A. Desenho**: evento (cancelamento efetivo), origem do tempo (primeira cobrança), corte fixo e censura à direita.
- **B. O erro clássico**: retenção ingênua por safra × Kaplan-Meier com IC 95% (log-log); metas editáveis; sem
  preencher M12/M18/M24 onde a safra não tem tempo de observação.
- **C. Comparações**: log-rank por canal, plano e safra; pares com correção de Holm.
- **D. Cox**: razões de risco com IC e C-index; teste de riscos proporcionais (Schoenfeld) que **mostra a violação**;
  correção (estratificação por plano + promoção por períodos + reajuste); tabela plantado × estimado.
- **E. Valor por canal**: RMST e LTV de **contribuição** (com margem) em 24 meses × CAC com incerteza, payback, IC por bootstrap e
  realocação de verba como **faixa de cenários**, separando **medido** de **projetado**.
- **F. O que poderia ter dado errado**: censura ignorada, riscos proporcionais violados, ranking por M12 bruto com safra pequena.
- **G. Riscos competitivos**: incidência acumulada voluntário × involuntário × fim de contrato (Aalen-Johansen).
- **H. Operação**: ponte de MRR, retenção líquida de receita (NRR/GRR), reativação, troca de plano e conversão de trial.
- **I. Quem tratar**: validação **fora do tempo**, score de risco por assinante, alvo da ação do mês 3 e desenho do teste A/B.
- **J. Fora do roteiro**: o mesmo pipeline num **dataset público** de churn e o mesmo modelo em dados com gerador diferente do modelo.
- **K. Limites honestos** (abaixo).

## Resultados

### A. Desenho

| Item | Valor |
|---|---|
| Assinantes sintéticos | 18.000 (seed 42) |
| Entradas | 01/11/2023 a 31/10/2026 |
| Corte de observação | 31/10/2026 |
| Cancelaram (evento) | 7.391 (41,1%) |
| Censurados à direita (ainda ativos) | 10.609 (58,9%) |
| Seguimento máximo possível | 36,0 meses |
| Assinantes com ≥ 12 / ≥ 18 / ≥ 24 meses possíveis | 10.909 / 8.286 / 5.213 |

Causas observadas: voluntário 5.634, involuntário (falha de pagamento) 1.068,
fim de contrato 689.

A janela de entrada cobre 36 meses para que M24 seja **observável** nas safras mais antigas
(M24 vem preenchido em 4 das 12 safras). Onde a safra não tem tempo de observação, a célula continua vazia.

### B. Ingênuo × Kaplan-Meier por safra

A "retenção ingênua" (ativos ÷ iniciados) só mede **há quanto tempo a safra entrou**: ela vai de
39% (S1) a 95% (S12)
e correlaciona −0,98 (Spearman) com a idade da safra. O KM em M3, comparável entre safras,
tem correlação +0,53 com a idade da safra: o que a conta ingênua mostra como "melhora" não é melhora.

| Safra | Entrada | n | Ingênua | KM M3 | KM M6 | KM M12 | KM M18 | KM M24 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| S1 | Nov/23–Jan/24 | 1.568 | 39% | 90,4% | 81,8% | 68,0% ▲ | 54,0% | 45,5% ▼ | 
| S2 | Fev/24–Abr/24 | 1.130 | 43% | 90,1% | 81,2% | 68,8% ▲ | 54,6% | 48,3% | 
| S3 | Mai/24–Jul/24 | 1.239 | 40% | 89,6% | 83,0% | 67,7% ▲ | 52,9% | 45,1% ▼ | 
| S4 | Ago/24–Out/24 | 1.276 | 42% | 87,9% | 81,1% | 69,0% ▲ | 54,6% | 47,4% | 
| S5 | Nov/24–Jan/25 | 1.800 | 43% | 88,5% | 78,3% | 64,8% | 49,7% ▼ | — | 
| S6 | Fev/25–Abr/25 | 1.243 | 49% | 87,0% | 78,8% | 65,3% | 51,1% ▼ | — | 
| S7 | Mai/25–Jul/25 | 1.356 | 54% | 88,9% | 81,0% | 68,2% ▲ | — | — | 
| S8 | Ago/25–Out/25 | 1.297 | 60% | 90,3% | 82,7% | 67,2% | — | — | 
| S9 | Nov/25–Jan/26 | 2.073 | 66% | 89,4% | 78,9% | — | — | — | 
| S10 | Fev/26–Abr/26 | 1.332 | 76% | 88,2% | 79,4% | — | — | — | 
| S11 | Mai/26–Jul/26 | 1.811 | 78% | 83,3% | — | — | — | — | 
| S12 | Ago/26–Out/26 | 1.875 | 95% | — | — | — | — | — | 

"—" = safra sem tempo de observação (não preenchida). ▲/▼ = IC 95% inteiro acima/abaixo da meta fictícia
(M12 65%, M18 55%, M24 48%; editáveis em `src/sobrevivencia/config.py`).

### C. Comparações (log-rank, Holm)

| Fator | χ² (gl) | p | Pares significativos (bruto → Holm) |
|---|---:|---:|---:|
| Canal | 615,9 (5) | < 0,001 | 15 → 15 de 15 |
| Plano | 336,7 (3) | < 0,001 | 6 → 6 de 6 |
| Safra | 86,2 (11) | < 0,001 | 25 → 13 de 66 |

Retenção KM em M12 por canal: Orgânico 70,6%; Busca paga 65,0%; Mídia paga (Meta) 55,0%; Social 59,6%; Indicação 79,2%; E-mail/CRM 74,8%.


### D. Cox: plantado × estimado

O modelo **ingênuo** (riscos proporcionais, um HR por covariável) viola a premissa: o teste de Schoenfeld rejeita
4 de 13 covariáveis (global p < 0,001). O modelo **corrigido**
(estratificado por plano, promoção por períodos, reajuste como efeito de calendário) não é rejeitado
(global p 0,749). C-index: 0,640 (ingênuo) e 0,622
(corrigido, só compara assinantes do mesmo plano).

| Efeito | Plantado | Cox ingênuo (IC 95%) | Cox corrigido (IC 95%) |
|---|---:|---:|---:|
| Canal: busca paga (vs orgânico) | 1,15 | 1,13 (1,05–1,21) | 1,12 (1,05–1,20) |
| Canal: mídia paga Meta (vs orgânico) | 1,50 | 1,46 (1,36–1,55) | 1,46 (1,37–1,56) |
| Canal: social (vs orgânico) | 1,20 | 1,28 (1,19–1,39) | 1,29 (1,19–1,39) |
| Canal: indicação (vs orgânico) | 0,70 | 0,75 (0,67–0,83) | 0,74 (0,66–0,83) |
| Canal: e-mail/CRM (vs orgânico) | 0,85 | 0,87 (0,80–0,95) | 0,88 (0,80–0,96) |
| Engajamento (+1 desvio-padrão) | 0,78 | 0,77 (0,76–0,79) | 0,78 (0,76–0,80) |
| Entrou pelo Passe Copa | 1,60 | 2,15 (1,81–2,56) | 1,60 (1,34–1,92) |
| Dispositivo: desktop (vs mobile) | 1,00 | 1,02 (0,97–1,07) | 1,02 (0,97–1,07) |
| Dispositivo: tablet (vs mobile) | 1,00 | 1,05 (0,96–1,14) | 1,04 (0,95–1,13) |
| Plano: combo (vs mensal) | 0,75 | 0,75 (0,71–0,80) | 0,76 (0,71–0,81)¹ |
| Plano: estudante (vs mensal) | 1,20 | 1,13 (1,07–1,20) | 1,19 (1,12–1,26)¹ |
| Plano: anual (vs mensal) | — | 0,58 (0,54–0,62) | — |
| Entrou na Black Friday (efeito único) | — | 1,14 (1,06–1,23) | — |
| Promoção vigente (meses 0–3) | 0,85 | — | 0,91 (0,78–1,05) |
| Penhasco (mês 3–4, 1º mês a preço cheio) | 3,00 | — | 2,64 (2,18–3,19) |
| Pós-penhasco (meses 4–6) | 1,35 | — | 1,31 (1,08–1,60) |
| Reajuste de preço (Mensal/Combo, jul–ago/26) | 1,50 | — | 1,62 (1,49–1,77) |

¹ HR de plano estimado num modelo complementar sem o plano anual (que é estratificado no modelo corrigido).
Cobertura dos IC 95% sobre os efeitos plantados: 100% no corrigido (13 efeitos) contra
91% no ingênuo.

**Validação em 20 réplicas** (seeds diferentes, mesmo gerador): o maior viés relativo médio entre os efeitos foi de
6,5% e os IC 95% cobriram o valor plantado em 93% dos
260 intervalos. Isso mostra que o resultado não depende da seed oficial, **não** que o modelo serve em dado real: o modelo corrigido
espelha a estrutura do gerador. As seções I e J tratam desse limite.

### E. Valor por canal (RMST, LTV de contribuição, CAC, payback)

O LTV é de **contribuição**: receita ao preço de tabela vigente (com o reajuste de jul/2026) × sobrevivência × desconto de 12% ao ano ×
margem de 66,5% por real de receita (70% de margem de contribuição menos 3,5% de custo de cobrança).

| Canal | CAC (premissa) | RMST 24m (meses) | LTV 24m (R$) | % medido | LTV/CAC (IC: bootstrap + CAC incerto) | Payback (mensalidades) |
|---|---:|---:|---:|---:|---:|---:|
| Orgânico * | R$ 30 | 16,9 (16,6–17,1) | R$ 329 (R$ 323–R$ 334) | 100% | n/c | 2 |
| Busca paga | R$ 95 | 15,8 (15,4–16,1) | R$ 309 (R$ 302–R$ 316) | 100% | 3,3× (2,5–4,5) | 6 |
| Mídia paga (Meta) | R$ 52 | 13,4 (13,1–13,8) | R$ 270 (R$ 263–R$ 277) | 100% | 5,2× (4,1–7,3) | 3 |
| Social | R$ 60 | 14,6 (14,2–15,0) | R$ 276 (R$ 267–R$ 286) | 100% | 4,6× (3,6–6,4) | 4 |
| Indicação | R$ 56 | 18,8 (18,3–19,3) | R$ 357 (R$ 347–R$ 367) | 100% | 6,4× (4,9–8,9) | 3 |
| E-mail/CRM * | R$ 22 | 18,0 (17,6–18,4) | R$ 362 (R$ 353–R$ 370) | 100% | n/c | 2 |

\* canal próprio, de capacidade limitada e custo alocado: **o LTV/CAC não é comparável** com o dos canais pagos (n/c) e o canal não entra na realocação de verba.
IC 95% por bootstrap de assinantes (1.000 réplicas); no LTV/CAC o CAC também varia 30% para cima e para baixo. **Medido** = parte do LTV coberta por Kaplan-Meier com pelo menos
30 assinantes sob risco; o resto é projeção de cauda com risco constante. ARPU, margem, CAC e taxa de desconto são **premissas**
(os CACs foram escolhidos para que a pergunta "CAC ou permanência?" tivesse uma resposta não trivial; ver [`DECISIONS.md`](DECISIONS.md)).

**Realocação de verba como faixa (projeção).** Mover R$ 100 mil de Busca paga para Indicação, conforme o CAC marginal de Indicação fique acima do médio:

| CAC marginal acima do médio | Valor líquido (estimativa) | IC 95% | Chance de ser positivo |
|---:|---:|---:|---:|
| 0% | R$ 312,2 mil | R$ 95,4 mil a R$ 581,7 mil | 100% |
| 25% | R$ 184,7 mil | −R$ 7,6 mil a R$ 407,2 mil | 96% |
| 50% | R$ 99,7 mil | −R$ 76,8 mil a R$ 290,2 mil | 82% |
| 100% | −R$ 6,5 mil | −R$ 163,7 mil a R$ 146,2 mil | 44% |

O ganho se anula quando o CAC marginal de Indicação chega a 96% acima do médio (IC 23% a 208%).

### F. O que poderia ter dado errado

1. **Censura ignorada**: na retenção M12 de toda a base (verdade plantada 65,9%), tratar censurado como
   cancelado dá 41%, descartar os censurados dá
   59%; o KM dá 66,0%.
2. **Riscos proporcionais violados**: o HR único da promoção (1,14) prevê
   4,4% de cancelamento no mês 3–4, mas o observado é
   10,5% (9,9% no modelo corrigido).
3. **Ranking por M12 bruto com safra pequena**: com 300 assinantes, o ranking bruto acerta o
   melhor canal em 63% dos 1.000 sorteios e o pior em
   58%.

### G. Riscos competitivos (Aalen-Johansen)

Até M18: voluntário 36,6%, involuntário 6,9%,
fim de contrato (só anual) 5,0%. "1 − KM tratando as outras causas como censura"
superestima o voluntário (38,9% contra 36,6% corretos).
O cancelamento involuntário (falha de pagamento) tem alavanca própria, que não é a da oferta: nova tentativa de cobrança e aviso antes do vencimento.

### H. Operação: MRR, retenção de receita, reativação, trial

A análise de sobrevivência olha o **primeiro** período de cada assinante. Esta camada (premissas fictícias de reativação, troca de plano e trial; fluxos aleatórios
independentes, então não muda a análise acima) mostra o que isso esconde. MRR de um assinante = preço pago no mês (com a promoção e o reajuste).

| Últimos 12 meses | R$ de MRR |
|---|---:|
| MRR no início | R$ 230.365 |
| + Novos | R$ 199.961 |
| + Reativações | R$ 7.558 |
| + Upgrade de plano | R$ 9.095 |
| + Fim da promoção (preço cheio) | R$ 10.730 |
| + Reajuste de preço | R$ 26.365 |
| − Downgrade | −R$ 2.051 |
| − Churn | −R$ 112.831 |
| **MRR no fim** | **R$ 369.193** (crescimento de 60%) |

- **Retenção líquida de receita (NRR) em 7.594 assinantes ativos em outubro de 2025**: 79,5% (IC 78,2% a 80,7%);
  a retenção bruta (GRR, sem expansão) é 70,7%. A expansão (upgrade, fim de promoção e reajuste) recupera 8,8% da receita da base, mas não o que o churn tirou.
- **Por canal (NRR)**: E-mail/CRM 90%; Indicação 90%; Orgânico 83%; Busca paga 76%; Social 75%; Mídia paga (Meta) 67%.
- **Reativação**: 10,3% dos cancelamentos voltam; por causa (em até 12 meses): Voluntário 7%; Involuntário (falha de pagamento) 34%; Fim de contrato (anual não renovado) 8%.
  Contando quem volta, a retenção em M12 sobe de 67,3% (só o primeiro período) para 69,6%.
- **Troca de plano**: 8,3% dos assinantes trocam de plano (1.497 trocas).
- **Conversão de trial** (premissa): 28,8% no total; por canal: Indicação 54%; E-mail/CRM 45%; Orgânico 38%; Busca paga 30%; Social 22%; Mídia paga (Meta) 18%.

### I. Quem tratar: fora do tempo, score e teste da ação

**Validação fora do tempo.** O modelo de score (Cox estratificado por plano) é ajustado só com o que se sabia em 31/10/2025 (seguimento truncado nessa data) e avaliado em
7.091 assinantes que entraram depois, cujo desfecho ele nunca viu e cujo período traz o reajuste de preço, o Passe Copa e as eleições, que o modelo não conhecia.

- C-index em 6 meses: 0,673 no treino e **0,667 no teste**. O **teto** (C-index do risco individual verdadeiro, que só existe porque os dados são sintéticos) é 0,675:
  nenhum modelo faria muito melhor, porque o tempo de vida tem muito acaso. Um C-index moderado é, neste caso, o esperado.
- O quinto de maior risco concentra 35% dos cancelamentos em 6 meses (lift 1,76×).
- **Calibração**: o modelo **subestima** o cancelamento no teste (M3: previsto 88,9%, observado 87,4%; M6: previsto 80,6%, observado 77,7%),
  porque não conhecia o reajuste de preço. O ranking de risco se mantém; os níveis exigem reajuste periódico do modelo.
- O score de cada assinante (probabilidade de cancelar em 6 meses e decil) é gravado em `data/score_risco.csv` por `run_all.py`.

**Quem tratar no mês 3.** Entre os 1.394 assinantes da Black Friday que chegam ao mês 3, o excesso de cancelamento atribuível ao penhasco é maior no terço de maior risco:

| Terço de risco | n | Cancela no mês 3–4 | Efetividade de equilíbrio |
|---|---:|---:|---:|
| menor risco | 465 | 7,5% | 30% |
| risco médio | 464 | 10,6% | 22% |
| maior risco | 465 | 13,3% | 17% |

Tratar todos rende R$ 3.288 líquidos (projeção); tratar só o terço de maior risco, R$ 1.885. Com 35% de efetividade assumida, vale tratar todos; a priorização por risco só importa se a capacidade
de contato for limitada.

**Como provar que a ação funciona (teste A/B).** Desfecho primário: cancelamento entre o mês 3 e o mês 4 entre quem chegou ao mês 3. Randomização: hash determinístico do id do assinante, 50/50, feita no início do mês 3. Nível 5% e poder 80%:

| Efetividade a detectar | Cancelamento no controle → tratamento | n por braço | Campanhas de Black Friday necessárias |
|---:|---:|---:|---:|
| 15% do excesso | 10,5% → 9,5% | 15.462 | 52,7 |
| 35% do excesso | 10,5% → 8,2% | 2.671 | 9,1 |
| 50% do excesso | 10,5% → 7,3% | 1.243 | 4,2 |

Com uma única campanha (587 assinantes no mês 3) o teste só detectaria uma efetividade de 94% do excesso. Conclusão prática: não dá para provar a ação numa Black Friday; é preciso
rodar o teste em **todas as saídas de promoção do ano**, ou aceitar um piloto com monitoramento e decisão por faixa de efetividade.

### J. Fora do roteiro: dataset público e gerador diferente

**Dataset público.** O mesmo pipeline roda numa amostra pública de churn de telecom publicada pela IBM (Apache-2.0; ver [`data_externo/LEIA-ME.md`](data_externo/LEIA-ME.md)), cujo processo gerador eu **não** plantei.
É dado de exemplo, não dado de operação, e é de telecom, não de jornal: os números abaixo não dizem nada sobre assinatura de notícias. 7.032 clientes, 26,6% cancelaram.

- **O primeiro mês pesa muito**: 20% de todos os cancelamentos acontecem no 1º mês de contrato (risco de 5,4% no mês), e 9,8% no contrato mensal.
- **Contrato**: retenção em M12 de 70,3% no contrato mensal contra 99,1% no de 1 ano e 100,0% no de 2 anos
  (log-rank p < 0,001; 3 de 3 pares significativos com Holm). Boa parte disso é mecânica (contrato com fidelidade), não "comportamento".
- **Fibra óptica**: HR 3,51 (IC 2,86 a 4,31) contra DSL, no modelo estratificado por contrato; cheque eletrônico, HR 1,63.
  A cobrança mensal sai com HR 0,44 (menor que 1), o que **não** significa que preço alto retém: ela é colinear com o tipo de internet, e o coeficiente só faz sentido junto com eles.
- **A correção que funcionou no sintético não resolve aqui**: estratificar por contrato não basta, e o teste de Schoenfeld ainda rejeita 7 de 9 covariáveis
  (global p < 0,001). Com 1.869 eventos o teste tem muito poder; o próximo passo seria efeitos que variam no tempo, não um HR único.
- **A definição do evento importa**: se a leitura fosse a de "tábua de período" (só quem cancelou no último mês), a retenção em M12 seria de 0,1%, absurda para uma base com clientes de até 72 meses.
  Só a leitura usual é coerente com o arquivo, mas a documentação do arquivo não resolve a dúvida.

**Gerador diferente do modelo.** O Cox corrigido espelha a estrutura do gerador oficial. Para ver o que acontece quando não espelha, o mesmo modelo foi ajustado em três tipos de dados
(6 réplicas de 9.000 assinantes cada): o gerador oficial (referência), um com heterogeneidade não observada entre assinantes e um com o penhasco fora do mês que o modelo supõe.

| Variante | Cobertura dos IC 95% | Maior viés relativo (efeito) |
|---|---:|---:|
| Mesmo gerador do modelo (referência) | 90% | 3% (Reajuste de preço (Mensal/Combo, jul–ago/26)) |
| Heterogeneidade não observada (fragilidade gama, variância 0.5) | 87% | 7% (Canal: mídia paga Meta (vs orgânico)) |
| Penhasco 15 dias depois do mês 3–4 que o modelo supõe | 78% | 36% (Penhasco (mês 3–4, 1º mês a preço cheio)) |

O modelo corrigido **depende de saber onde o penhasco está**: com o efeito fora do mês 3–4 que o modelo supõe, a cobertura cai para 78% (contra 90% na referência)
e o efeito mais distorcido é "Penhasco (mês 3–4, 1º mês a preço cheio)" (1,91 estimado contra 3,00 plantado).
Isso é um limite do método, não um detalhe: um modelo que acerta no gerador que o espelha pode errar quando a realidade não coincide com a especificação.

### K. Limites honestos

- **Dados sintéticos e efeitos plantados.** O projeto mostra que o método recupera o efeito certo (tabela D) e se comporta de forma previsível quando o gerador é diferente (seção J), não que
  mídia paga seja pior ou que a Black Friday tenha um penhasco no mundo real. O dataset público é dado de exemplo de outro setor.
- **Premissas de valor**: ARPU = preço de tabela vigente por plano, margem de contribuição, custo de cobrança, CAC por canal, taxa de desconto, custo e efetividade da ação do mês 3
  são premissas minhas, em `src/sobrevivencia/config.py` e listadas em [`DECISIONS.md`](DECISIONS.md). **O CAC foi escolhido para a pergunta "CAC ou permanência?" ter resposta não trivial**; por isso a conclusão de canal é apresentada com o CAC incerto e como faixa.
- **CAC médio ≠ CAC marginal**: a realocação é mostrada para vários CAC marginais, e o ponto de equilíbrio está no texto.
- **A camada de operação (seção H) usa premissas fictícias** de reativação, troca de plano e trial; ela mostra a mecânica de medir (ponte de MRR, NRR), não taxas reais. A análise de sobrevivência segue olhando só o primeiro período.
- O KM assume censura não informativa; como há efeitos de calendário (reajuste, Copa), o KM agregado mistura safras com riscos diferentes.
- O modelo fora do tempo subestima o cancelamento depois de um evento que não viu (reajuste de preço): em produção, precisa de reajuste periódico.
- **Não foi feito**: modelos de fragilidade ou de cura, múltiplas reativações, efeito dos upgrades sobre o risco, efeito causal do reajuste (só associação), efeitos que variam no tempo para o dataset público e validação com dado de operação real.

## Como defender cada escolha

[`GUIA_DE_DEFESA.md`](GUIA_DE_DEFESA.md) explica, em perguntas e respostas, por que Kaplan-Meier com IC log-log, log-rank com Holm, Cox com Efron, o teste de Schoenfeld por faixas, RMST, Aalen-Johansen,
a validação fora do tempo e o que o projeto **não** prova.

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
(`report/`, copiado para `docs/` para a página online), os documentos (este README, `DECISIONS.md`, `GUIA_DE_DEFESA.md`, `portfolio/`) e executa os notebooks. Opções: `--rapido` (menos réplicas de bootstrap),
`--sem-notebooks`, `--sem-gate`.

## Relatório interativo

[`report/sobrevivencia-assinaturas.html`](report/sobrevivencia-assinaturas.html) é um arquivo único, sem CDN e sem servidor (HTML + CSS + JavaScript puro, figuras
embutidas, modo noturno) com um **explorador**: escolha canal, plano, safra e horizonte (M12/M18/M24), veja a curva com IC e edite a linha de meta.
Ele também está publicado online (links no topo deste arquivo).

## Estrutura

```
├── README.md · DECISIONS.md · GUIA_DE_DEFESA.md · LICENSE · requirements.txt · pyproject.toml
├── run_all.py                    # gera dados, análises, figuras, results.json e documentos
├── src/sobrevivencia/            # pacote: config, simulate, km, cohorts, cox, value, operacao, preditivo, externo, ...
├── templates/                    # modelos (README, DECISIONS, guia, relatório, case): números só via placeholders
├── data_externo/                 # dataset público de churn (com origem, licença e SHA-256)
├── results/                      # results.json (fonte única) e ground_truth.json (verdade plantada)
├── reports/figures/              # PNGs
├── report/ · docs/               # relatório HTML autônomo (docs/ alimenta a página online)
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
estudo, as premissas e os critérios de aceite; a IA escreveu e testou o código a partir dessas instruções. O histórico do Git mostra o Claude como coautor dos commits, de propósito.
Por isso existe o [`GUIA_DE_DEFESA.md`](GUIA_DE_DEFESA.md): cada escolha técnica está explicada para eu defendê-la sem consulta. Os dados são sintéticos e os resultados
não representam nenhuma empresa real.

Licença: MIT.
