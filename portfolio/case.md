---
slug: sobrevivencia-assinaturas
titulo: "Sobrevivência de assinantes: onde a retenção quebra"
categoria: Estatística aplicada
tipo_de_dado: Sintético
periodo: "novembro de 2023 a outubro de 2026, corte em 31/10/2026"
meu_papel: Projeto pessoal de análise estatística, com apoio de IA
stack_completa: Python, pandas, NumPy, SciPy, lifelines, statsmodels, Matplotlib, Jupyter, pytest
tecnologias: [Python, pandas, lifelines]
demo: /demos/sobrevivencia-assinaturas.html
codigo: https://github.com/GabrielRangel101/survival-assinaturas
card: "Sobrevivência de assinantes: Kaplan-Meier, Cox com riscos proporcionais violados e corrigidos, LTV por canal com CAC incerto, MRR e NRR, validação fora do tempo e em dado público, 160 testes. Dados sintéticos, código aberto."
---

# Sobrevivência de assinantes: onde a retenção quebra

Análise de sobrevivência aplicada à retenção de assinaturas de um jornal digital fictício (Gazeta Meridiano): quanto tempo cada tipo de
assinante permanece, onde a retenção quebra (no fim da promoção, por exemplo) e qual canal vale a verba quando se considera permanência, e não só
custo de aquisição. A decisão em jogo era onde colocar a verba de aquisição e o que fazer no mês 3 da promoção da Black Friday.

Os dados são 100% sintéticos, gerados por scripts em Python com semente fixa, e os efeitos foram plantados de propósito: mídia paga com risco maior,
indicação menor, engajamento protetor e um penhasco de risco no mês seguinte ao fim da promoção (que viola os riscos proporcionais de propósito). O que o
projeto mostra é que o método recupera o efeito certo, e não uma descoberta sobre o mundo real. Como isso é circular, o projeto também valida o modelo fora do tempo,
roda o mesmo pipeline num dataset público de churn (dado de exemplo de telecom, que eu não plantei) e mede o que acontece quando o gerador não espelha o modelo.
O código foi escrito com apoio do Claude, sob minha direção, e a demo é um relatório estático com um explorador interativo de curvas de sobrevivência.

## Problema

A retenção "ativos ÷ iniciados" por safra parece boa, mas só mede há quanto tempo a safra entrou: ela vai de 39% a
95% entre a safra mais antiga e a mais recente. Além disso, comparar canais só pelo custo de aquisição ignora quanto tempo
cada assinante fica.

## Decisão

Defini o evento (cancelamento efetivo), a origem do tempo (primeira cobrança) e o corte antes de olhar o resultado, tratei a censura à direita com Kaplan-Meier
e IC 95% log-log, deixei vazias as células de M12, M18 e M24 sem tempo de observação e testei a premissa de riscos proporcionais antes de confiar no Cox. O valor por canal
usa RMST e LTV de contribuição (com margem) contra um CAC incerto, com IC por bootstrap de assinantes e a parte medida separada da projetada.

## O que a análise mostra

Retenção: por Kaplan-Meier, a base retém 66,0% em M12 (IC 95% 65,2% a 66,8%), acima da meta fictícia
de 65%; 51,6% em M18 (abaixo da meta de 55%) e
44,1% em M24 (IC 43,2% a 45,1%, abaixo da meta de 48%).
M24 só é observável nas safras mais antigas (4 de 12); nas demais a célula fica vazia. O log-rank separa canais (p < 0,001) e planos (p < 0,001).

Onde quebra: 10,5% de quem chegou ao mês 3 da Black Friday cancela no mês seguinte ao fim da promoção, contra 3,9% sem promoção.
O Cox corrigido estima HR 2,64 (IC 95% 2,18 a 3,19) para o penhasco, perto do 3,00 plantado; o Cox ingênuo, com HR único de 1,14, subestima o
penhasco e o teste de Schoenfeld por faixas de idade detecta a violação (p < 0,001).

Canais: Mídia paga (Meta) é o canal pago mais barato (R$ 52), mas o LTV de contribuição em 24 meses é de R$ 270 contra R$ 357 de Indicação.
Com o CAC variando 30% para cima e para baixo, o retorno por real é de 5,2× (IC 4,1 a 7,3)
contra 6,4× (IC 4,9 a 8,9), e Indicação é o melhor em 71% das réplicas:
uma vantagem moderada, que depende de um CAC que é premissa (escolhi os CACs para a pergunta ter resposta não trivial).

Projeção, não medição: mover R$ 100 mil de Busca paga para Indicação soma de R$ 312,2 mil (CAC marginal igual ao médio; IC R$ 95,4 mil a R$ 581,7 mil) até
R$ 99,7 mil (CAC marginal 50% acima), e deixa de compensar quando o CAC marginal passa de 96% acima do médio.
No mês 3 da promoção, uma ação de R$ 4 por assinante rende R$ 1.388 líquidos numa coorte de 673 assinantes, e só se paga se evitar mais de 22% do excesso de cancelamentos;
provar 35% de efetividade num teste A/B exige cerca de 2.671 assinantes por braço, mais do que uma campanha inteira.

Validação além do gerador: fora do tempo (modelo treinado até 31/10/2025, testado em quem entrou depois), o C-index é 0,667 contra um teto de 0,675 do risco verdadeiro, e o modelo subestima o cancelamento
porque não conhecia o reajuste de preço. No dataset público de churn, o primeiro mês concentra 20% dos cancelamentos e a correção que funcionou no sintético não resolve a violação de riscos proporcionais.
Com o gerador diferente do modelo, a cobertura dos IC cai de 90% para 78% quando o penhasco está fora do mês que o modelo supõe.

## Impacto real

Sem impacto medido em operação real: os dados são sintéticos e o valor em R$ é uma projeção feita com premissas declaradas (preço de tabela vigente como ARPU, margem de contribuição de 70%, CAC por canal, taxa de desconto de
12% ao ano), não um resultado.

## Destaques

- Retenção ingênua × Kaplan-Meier por safra, com M12, M18 e M24 vazios onde a safra não tem tempo de observação
- Log-rank por canal, plano e safra, com pares corrigidos por Holm (25 de 66 pares entre safras significativos sem correção, 13 com Holm)
- Cox com violação de riscos proporcionais mostrada (Schoenfeld) e corrigida (estrato por plano, promoção por períodos), com tabela de efeito plantado × estimado (100% dos IC 95% cobrem o valor plantado)
- Validação em 20 réplicas de seed: IC 95% cobrindo o efeito plantado em 93% dos casos
- LTV de contribuição por canal contra um CAC incerto, com payback, IC por bootstrap, ponto de equilíbrio e realocação de verba como faixa de cenários
- Ponte de MRR, retenção líquida de receita (NRR 80%), reativação, troca de plano e conversão de trial
- Validação fora do tempo, score de risco por assinante, alvo da ação do mês 3 e desenho do teste A/B
- Mesmo pipeline num dataset público de churn e o mesmo modelo em dados com gerador diferente
- Seção "O que poderia ter dado errado": censura ignorada, riscos proporcionais violados e ranking por M12 bruto com safra pequena
- Riscos competitivos (voluntário × involuntário × fim de contrato) por Aalen-Johansen
- Relatório HTML único, sem CDN, com modo noturno e explorador interativo (canal, plano, safra, horizonte e meta editável)

## Tecnologias utilizadas

Python, pandas, NumPy, SciPy, lifelines, statsmodels, Matplotlib, Jupyter, pytest

## Meu papel

Projeto pessoal de análise estatística, com apoio de IA

## Como foi feito

### Dados e reprodutibilidade

O gerador usa numpy com semente 42 e parâmetros centralizados em um arquivo de configuração. A duração vem de um modelo de risco por partes (exponencial por intervalos) em grade diária, com o risco mensal-base de
3,5%. São 18.000 assinantes, 59% deles censurados à direita no corte de 31/10/2026. Os efeitos plantados ficam gravados em um arquivo de verdade (`ground_truth.json`).

### Fonte única de números

Todo número do README, do relatório e deste texto é renderizado a partir de `results.json` por um template; um teste confere que nenhum número foi digitado à mão.

### Testes e verificação

A suíte pytest (160 testes) cobre determinismo da seed, invariantes de censura, Kaplan-Meier e log-rank contra exemplos calculados à mão e contra o lifelines, recuperação dos efeitos plantados (HR dentro da tolerância e IC cobrindo a verdade),
detecção da violação de riscos proporcionais, a ponte de MRR (fecha em todos os meses), a validação fora do tempo e a coerência entre `results.json` e os documentos. Há dois notebooks executáveis de ponta a ponta.

## Limites

Dados sintéticos não provam nada sobre uma empresa real, e os efeitos foram plantados: o projeto mostra que o método os recupera e quanto ele erra quando o gerador não espelha o modelo. O dataset público é dado de exemplo de outro setor.
O KM agregado mistura safras com riscos diferentes. ARPU, margem, CAC, taxa de desconto, a camada de operação (reativação, troca de plano, trial) e a efetividade da ação do mês 3 são premissas, e a realocação de verba depende do CAC marginal, mostrado como cenários.
Ficaram de fora modelos de fragilidade, efeitos que variam no tempo no dataset público, validação com dado de operação real e o efeito causal do reajuste.
