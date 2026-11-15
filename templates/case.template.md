---
slug: sobrevivencia-assinaturas
titulo: "Sobrevivência de assinantes: onde a retenção quebra"
categoria: Estatística aplicada
tipo_de_dado: Sintético
periodo: "{{ premissas.entrada_ini|mes_ano }} a {{ premissas.entrada_fim|mes_ano }}, corte em {{ premissas.corte|data }}"
meu_papel: Projeto pessoal de análise estatística, com apoio de IA
stack_completa: Python, pandas, NumPy, SciPy, lifelines, statsmodels, Matplotlib, Jupyter, pytest
tecnologias: [Python, pandas, lifelines]
demo: /demos/sobrevivencia-assinaturas.html
codigo: https://github.com/GabrielRangel101/survival-assinaturas
card: "{% filter trim %}{% include 'card.template.txt' %}{% endfilter %}"
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

A retenção "ativos ÷ iniciados" por safra parece boa, mas só mede há quanto tempo a safra entrou: ela vai de {{ d.ingenua_pior.ret_ingenua|pct(0) }} a
{{ d.ingenua_melhor.ret_ingenua|pct(0) }} entre a safra mais antiga e a mais recente. Além disso, comparar canais só pelo custo de aquisição ignora quanto tempo
cada assinante fica.

## Decisão

Defini o evento (cancelamento efetivo), a origem do tempo (primeira cobrança) e o corte antes de olhar o resultado, tratei a censura à direita com Kaplan-Meier
e IC 95% log-log, deixei vazias as células de M12/M18/M24 sem tempo de observação e testei a premissa de riscos proporcionais antes de confiar no Cox. O valor por canal
usa RMST e LTV descontado contra o CAC, com IC por bootstrap de assinantes e a parte medida separada da projetada.

## O que a análise mostra

Retenção: em M12 a base retém {{ ingenuo_vs_km.global.m12.valor|pct }} (IC 95% {{ ingenuo_vs_km.global.m12.lo|pct }} a {{ ingenuo_vs_km.global.m12.hi|pct }}), {{ d.status_txt[ingenuo_vs_km.global.m12.status] }} meta fictícia
de {{ premissas.metas.m12|pct(0) }}; em M18, {{ ingenuo_vs_km.global.m18.valor|pct }}, {{ d.status_txt[ingenuo_vs_km.global.m18.status] }} meta de {{ premissas.metas.m18|pct(0) }}. M24 não é observável com este desenho
({{ dados.n_com_24m_possiveis|int }} assinantes com 24 meses possíveis). O log-rank separa canais (p {{ comparacoes.canal.logrank.p|p }}) e planos (p {{ comparacoes.plano.logrank.p|p }}).

Onde quebra: {{ acao_mes3.medido.q_penhasco|pct }} de quem chegou ao mês 3 da Black Friday cancela no mês seguinte ao fim da promoção, contra {{ armadilhas.riscos_proporcionais.q_base_mes3|pct }} sem promoção.
O Cox corrigido estima HR {{ d.pen.hr|hr }} (IC 95% {{ d.pen.hr_lo|hr }} a {{ d.pen.hr_hi|hr }}) para o penhasco, perto do {{ premissas.hr_plantado.promo.promo_penhasco|hr }} plantado; o Cox ingênuo, com HR único de {{ d.hr_bf.hr|hr }}, subestima o
penhasco e o teste de Schoenfeld por faixas de idade detecta a violação (p {{ armadilhas.riscos_proporcionais.p_faixas_ingenuo|p }}).

Canais: {{ d.canal_mais_barato.rotulo }} é o canal pago mais barato ({{ d.canal_mais_barato.cac|brl }}), mas o LTV descontado em {{ premissas.horizonte_ltv }} meses é de {{ d.canal_midia.ltv.est|brl }} contra {{ d.canal_melhor.ltv.est|brl }} de {{ d.canal_melhor.rotulo }}; o retorno por real
é de {{ d.canal_midia.ltv_cac.est|n(1) }}× contra {{ d.canal_melhor.ltv_cac.est|n(1) }}×. {{ d.canal_pior.rotulo }} tem o pior retorno entre os canais com verba ({{ d.canal_pior.ltv_cac.est|n(1) }}×).

Projeção, não medição: mover R$ {{ premissas.verba_exemplo|int }} de {{ d.canal_pior.rotulo }} para {{ d.canal_melhor.rotulo }} soma cerca de {{ decisao_verba.ganho_realocar_pior_para_melhor|brl_mi }} de valor líquido (LTV − CAC), supondo CAC médio igual ao marginal.
No mês 3 da promoção, uma ação de {{ acao_mes3.projetado.custo_por_assinante|brl }} por assinante rende {{ acao_mes3.projetado.base.liquido|brl }} líquidos numa coorte de {{ acao_mes3.projetado.n_coorte|int }} assinantes, e só se paga se evitar mais de {{ acao_mes3.projetado.efetividade_equilibrio|pct(0) }} do excesso de cancelamentos.

## Impacto real

Sem impacto medido em operação real: os dados são sintéticos e o valor em R$ é uma projeção feita com premissas declaradas (preço de tabela como ARPU, CAC por canal, taxa de desconto de
{{ premissas.taxa_desconto_anual|pct(0) }} ao ano, sem margem de contribuição), não um resultado.

## Destaques

- Retenção ingênua × Kaplan-Meier por safra, com M12/M18/M24 vazios onde a safra não tem tempo de observação
- Log-rank por canal, plano e safra, com pares corrigidos por Holm ({{ comparacoes.safra.n_sig_bruto }} de {{ comparacoes.safra.n_pares }} pares entre safras significativos sem correção, {{ comparacoes.safra.n_sig_holm }} com Holm)
- Cox com violação de riscos proporcionais mostrada (Schoenfeld) e corrigida (estrato por plano, promoção por períodos), com tabela de efeito plantado × estimado ({{ cox.cobertura.corrigido|pct(0) }} dos IC 95% cobrem o valor plantado)
{% if recuperacao_mc is defined %}
- Validação em {{ recuperacao_mc.n_replicas|int }} réplicas de seed: IC 95% cobrindo o efeito plantado em {{ recuperacao_mc.cobertura_total|pct(0) }} dos casos
{% endif %}
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

O gerador usa numpy com semente {{ premissas.seed }} e parâmetros centralizados em um arquivo de configuração. A duração vem de um modelo de risco por partes (exponencial por intervalos) em grade diária, com o risco mensal-base de
{{ premissas.risco_mensal_base|pct }}. São {{ dados.n|int }} assinantes, {{ dados.pct_censurados|pct(0) }} deles censurados à direita no corte de {{ premissas.corte|data }}. Os efeitos plantados ficam gravados em um arquivo de verdade (`ground_truth.json`).

### Fonte única de números

Todo número do README, do relatório e deste texto é renderizado a partir de `results.json` por um template; um teste confere que nenhum número foi digitado à mão.

### Testes e verificação

A suíte pytest ({{ meta.n_testes|int }} testes) cobre determinismo da seed, invariantes de censura, Kaplan-Meier e log-rank contra exemplos calculados à mão e contra o lifelines, recuperação dos efeitos plantados (HR dentro da tolerância e IC cobrindo a verdade),
detecção da violação de riscos proporcionais e a coerência entre `results.json` e os documentos. Há dois notebooks executáveis de ponta a ponta.

## Limites

Dados sintéticos não provam nada sobre uma empresa real, e os efeitos foram plantados: o projeto mostra que o método os recupera. M24 não é observável com esta janela e o KM agregado mistura safras com riscos diferentes. ARPU, CAC, taxa de desconto e a efetividade da ação do mês 3 são premissas,
e a realocação de verba supõe CAC marginal igual ao médio. Ficaram de fora modelos de fragilidade, reativações, upgrade de plano e o efeito causal do reajuste.
