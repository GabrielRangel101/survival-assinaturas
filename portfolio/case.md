---
slug: sobrevivencia-assinaturas
titulo: "Sobrevivência de assinantes: onde a retenção quebra"
categoria: Estatística aplicada
tipo_de_dado: Sintético
periodo: "novembro de 2024 a outubro de 2026, corte em 31/10/2026"
meu_papel: Projeto pessoal de análise estatística, com apoio de IA
stack_completa: Python, pandas, NumPy, SciPy, lifelines, statsmodels, Matplotlib, Jupyter, pytest
tecnologias: [Python, pandas, lifelines]
demo: /demos/sobrevivencia-assinaturas.html
codigo: https://github.com/GabrielRangel101/survival-assinaturas
card: "Análise de sobrevivência da retenção de assinantes: Kaplan-Meier, log-rank com Holm, Cox com riscos proporcionais violados e corrigidos, RMST/LTV por canal e riscos competitivos, com 106 testes. Dados sintéticos, código aberto."
---

# Sobrevivência de assinantes: onde a retenção quebra

Análise de sobrevivência aplicada à retenção de assinaturas de um jornal digital fictício (Gazeta Meridiano): quanto tempo cada tipo de
assinante permanece, onde a retenção quebra (no fim da promoção, por exemplo) e qual canal vale a verba quando se considera permanência, e não só
custo de aquisição. A decisão em jogo era onde colocar a verba de aquisição e o que fazer no mês 3 da promoção da Black Friday.

Os dados são 100% sintéticos, gerados por scripts em Python com semente fixa, e os efeitos foram plantados de propósito: mídia paga com risco maior,
indicação menor, engajamento protetor e um penhasco de risco no mês seguinte ao fim da promoção (que viola os riscos proporcionais de propósito). O que o
projeto mostra é que o método recupera o efeito certo, e não uma descoberta sobre o mundo real. O código foi escrito com apoio do Claude, sob minha direção,
e a demo é um relatório estático com um explorador interativo de curvas de sobrevivência.

## Problema

A retenção "ativos ÷ iniciados" por safra parece boa, mas só mede há quanto tempo a safra entrou: ela vai de 45% a
94% entre a safra mais antiga e a mais recente. Além disso, comparar canais só pelo custo de aquisição ignora quanto tempo
cada assinante fica.

## Decisão

Defini o evento (cancelamento efetivo), a origem do tempo (primeira cobrança) e o corte antes de olhar o resultado, tratei a censura à direita com Kaplan-Meier
e IC 95% log-log, deixei vazias as células de M12/M18/M24 sem tempo de observação e testei a premissa de riscos proporcionais antes de confiar no Cox. O valor por canal
usa RMST e LTV descontado contra o CAC, com IC por bootstrap de assinantes e a parte medida separada da projetada.

## O que a análise mostra

Retenção: em M12 a base retém 66,1% (IC 95% 65,1% a 67,1%), acima da meta fictícia
de 65%; em M18, 51,0%, abaixo da meta de 55%. M24 não é observável com este desenho
(0 assinantes com 24 meses possíveis). O log-rank separa canais (p < 0,001) e planos (p < 0,001).

Onde quebra: 10,3% de quem chegou ao mês 3 da Black Friday cancela no mês seguinte ao fim da promoção, contra 3,6% sem promoção.
O Cox corrigido estima HR 2,85 (IC 95% 2,26 a 3,61) para o penhasco, perto do 3,00 plantado; o Cox ingênuo, com HR único de 1,20, subestima o
penhasco e o teste de Schoenfeld por faixas de idade detecta a violação (p < 0,001).

Canais: Mídia paga (Meta) é o canal pago mais barato (R$ 52), mas o LTV descontado em 24 meses é de R$ 369 contra R$ 498 de Indicação; o retorno por real
é de 7,1× contra 8,9×. Busca paga tem o pior retorno entre os canais com verba (4,4×).

Projeção, não medição: mover R$ 100.000 de Busca paga para Indicação soma cerca de R$ 444,3 mil de valor líquido (LTV − CAC), supondo CAC médio igual ao marginal.
No mês 3 da promoção, uma ação de R$ 4 por assinante rende R$ 2.565 líquidos numa coorte de 637 assinantes, e só se paga se evitar mais de 16% do excesso de cancelamentos.

## Impacto real

Sem impacto medido em operação real: os dados são sintéticos e o valor em R$ é uma projeção feita com premissas declaradas (preço de tabela como ARPU, CAC por canal, taxa de desconto de
12% ao ano, sem margem de contribuição), não um resultado.

## Destaques

- Retenção ingênua × Kaplan-Meier por safra, com M12/M18/M24 vazios onde a safra não tem tempo de observação
- Log-rank por canal, plano e safra, com pares corrigidos por Holm (12 de 28 pares entre safras significativos sem correção, 5 com Holm)
- Cox com violação de riscos proporcionais mostrada (Schoenfeld) e corrigida (estrato por plano, promoção por períodos), com tabela de efeito plantado × estimado (100% dos IC 95% cobrem o valor plantado)
- Validação em 20 réplicas de seed: IC 95% cobrindo o efeito plantado em 97% dos casos
- RMST e LTV descontado por canal contra o CAC, com payback e IC por bootstrap
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
3,5%. São 12.000 assinantes, 67% deles censurados à direita no corte de 31/10/2026. Os efeitos plantados ficam gravados em um arquivo de verdade (`ground_truth.json`).

### Fonte única de números

Todo número do README, do relatório e deste texto é renderizado a partir de `results.json` por um template; um teste confere que nenhum número foi digitado à mão.

### Testes e verificação

A suíte pytest (106 testes) cobre determinismo da seed, invariantes de censura, Kaplan-Meier e log-rank contra exemplos calculados à mão e contra o lifelines, recuperação dos efeitos plantados (HR dentro da tolerância e IC cobrindo a verdade),
detecção da violação de riscos proporcionais e a coerência entre `results.json` e os documentos. Há dois notebooks executáveis de ponta a ponta.

## Limites

Dados sintéticos não provam nada sobre uma empresa real, e os efeitos foram plantados: o projeto mostra que o método os recupera. M24 não é observável com esta janela e o KM agregado mistura safras com riscos diferentes. ARPU, CAC, taxa de desconto e a efetividade da ação do mês 3 são premissas,
e a realocação de verba supõe CAC marginal igual ao médio. Ficaram de fora modelos de fragilidade, reativações, upgrade de plano e o efeito causal do reajuste.
