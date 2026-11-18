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
projeto mostra é que o método recupera o efeito certo, e não uma descoberta sobre o mundo real. Como isso é circular, o projeto também valida o modelo fora do tempo,
roda o mesmo pipeline num dataset público de churn (dado de exemplo de telecom, que eu não plantei) e mede o que acontece quando o gerador não espelha o modelo.
O código foi escrito com apoio do Claude, sob minha direção, e a demo é um relatório estático com um explorador interativo de curvas de sobrevivência.

## Problema

A retenção "ativos ÷ iniciados" por safra parece boa, mas só mede há quanto tempo a safra entrou: ela vai de {{ d.ingenua_pior.ret_ingenua|pct(0) }} a
{{ d.ingenua_melhor.ret_ingenua|pct(0) }} entre a safra mais antiga e a mais recente. Além disso, comparar canais só pelo custo de aquisição ignora quanto tempo
cada assinante fica.

## Decisão

Defini o evento (cancelamento efetivo), a origem do tempo (primeira cobrança) e o corte antes de olhar o resultado, tratei a censura à direita com Kaplan-Meier
e IC 95% log-log, deixei vazias as células de M12, M18 e M24 sem tempo de observação e testei a premissa de riscos proporcionais antes de confiar no Cox. O valor por canal
usa RMST e LTV de contribuição (com margem) contra um CAC incerto, com IC por bootstrap de assinantes e a parte medida separada da projetada.

## O que a análise mostra

Retenção: por Kaplan-Meier, a base retém {{ ingenuo_vs_km.global.m12.valor|pct }} em M12 (IC 95% {{ ingenuo_vs_km.global.m12.lo|pct }} a {{ ingenuo_vs_km.global.m12.hi|pct }}), {{ d.status_txt[ingenuo_vs_km.global.m12.status] }} meta fictícia
de {{ premissas.metas.m12|pct(0) }}; {{ ingenuo_vs_km.global.m18.valor|pct }} em M18 ({{ d.status_txt[ingenuo_vs_km.global.m18.status] }} meta de {{ premissas.metas.m18|pct(0) }}) e
{{ ingenuo_vs_km.global.m24.valor|pct }} em M24 (IC {{ ingenuo_vs_km.global.m24.lo|pct }} a {{ ingenuo_vs_km.global.m24.hi|pct }}, {{ d.status_txt[ingenuo_vs_km.global.m24.status] }} meta de {{ premissas.metas.m24|pct(0) }}).
M24 só é observável nas safras mais antigas ({{ ingenuo_vs_km.n_celulas_m24_preenchidas }} de {{ premissas.n_safras }}); nas demais a célula fica vazia. O log-rank separa canais (p {{ comparacoes.canal.logrank.p|p }}) e planos (p {{ comparacoes.plano.logrank.p|p }}).

Onde quebra: {{ acao_mes3.medido.q_penhasco|pct }} de quem chegou ao mês 3 da Black Friday cancela no mês seguinte ao fim da promoção, contra {{ armadilhas.riscos_proporcionais.q_base_mes3|pct }} sem promoção.
O Cox corrigido estima HR {{ d.pen.hr|hr }} (IC 95% {{ d.pen.hr_lo|hr }} a {{ d.pen.hr_hi|hr }}) para o penhasco, perto do {{ premissas.hr_plantado.promo.promo_penhasco|hr }} plantado; o Cox ingênuo, com HR único de {{ d.hr_bf.hr|hr }}, subestima o
penhasco e o teste de Schoenfeld por faixas de idade detecta a violação (p {{ armadilhas.riscos_proporcionais.p_faixas_ingenuo|p }}).

Canais: {{ d.canal_mais_barato.rotulo }} é o canal pago mais barato ({{ d.canal_mais_barato.cac|brl }}), mas o LTV de contribuição em {{ premissas.horizonte_ltv }} meses é de {{ d.canal_midia.ltv.est|brl }} contra {{ d.canal_melhor.ltv.est|brl }} de {{ d.canal_melhor.rotulo }}.
Com o CAC variando {{ premissas.cac_incerteza|pct(0) }} para cima e para baixo, o retorno por real é de {{ d.canal_midia.ltv_cac_incerteza.est|n(1) }}× (IC {{ d.canal_midia.ltv_cac_incerteza.lo|n(1) }} a {{ d.canal_midia.ltv_cac_incerteza.hi|n(1) }})
contra {{ d.canal_melhor.ltv_cac_incerteza.est|n(1) }}× (IC {{ d.canal_melhor.ltv_cac_incerteza.lo|n(1) }} a {{ d.canal_melhor.ltv_cac_incerteza.hi|n(1) }}), e {{ d.canal_melhor.rotulo }} é o melhor em {{ d.canal_melhor.prob_melhor_ltv_cac|pct(0) }} das réplicas:
uma vantagem moderada, que depende de um CAC que é premissa (escolhi os CACs para a pergunta ter resposta não trivial).

Projeção, não medição: mover {{ premissas.verba_exemplo|brl_mi }} de {{ d.real_origem.rotulo }} para {{ d.real_destino.rotulo }} soma de {{ d.real.linhas[0].ganho|brl_mi }} (CAC marginal igual ao médio; IC {{ d.real.linhas[0].lo|brl_mi }} a {{ d.real.linhas[0].hi|brl_mi }}) até
{{ d.real.linhas[2].ganho|brl_mi }} (CAC marginal {{ d.real.linhas[2].premio|pct(0) }} acima), e deixa de compensar quando o CAC marginal passa de {{ d.real.premio_equilibrio|pct(0) }} acima do médio.
No mês 3 da promoção, uma ação de {{ acao_mes3.projetado.custo_por_assinante|brl }} por assinante rende {{ acao_mes3.projetado.base.liquido|brl }} líquidos numa coorte de {{ acao_mes3.projetado.n_coorte|int }} assinantes, e só se paga se evitar mais de {{ acao_mes3.projetado.efetividade_equilibrio|pct(0) }} do excesso de cancelamentos;
provar {{ d.teste.linhas[1].efetividade|pct(0) }} de efetividade num teste A/B exige cerca de {{ d.teste.linhas[1].n_por_braco|int }} assinantes por braço, mais do que uma campanha inteira.

Validação além do gerador: fora do tempo (modelo treinado até {{ d.fora.t0|data }}, testado em quem entrou depois), o C-index é {{ d.fora.cindex.teste|n(3) }} contra um teto de {{ d.fora.cindex.teto_verdadeiro|n(3) }} do risco verdadeiro, e o modelo subestima o cancelamento
porque não conhecia o reajuste de preço. No dataset público de churn, o primeiro mês concentra {{ d.ext.primeiro_mes.pct_de_todos_cancelamentos|pct(0) }} dos cancelamentos e a correção que funcionou no sintético não resolve a violação de riscos proporcionais.
Com o gerador diferente do modelo, a cobertura dos IC cai de {{ d.rob.oficial.cobertura_total|pct(0) }} para {{ d.rob.penhasco_deslocado.cobertura_total|pct(0) }} quando o penhasco está fora do mês que o modelo supõe.

## Impacto real

Sem impacto medido em operação real: os dados são sintéticos e o valor em R$ é uma projeção feita com premissas declaradas (preço de tabela vigente como ARPU, margem de contribuição de {{ premissas.margem.contribuicao|pct(0) }}, CAC por canal, taxa de desconto de
{{ premissas.taxa_desconto_anual|pct(0) }} ao ano), não um resultado.

## Destaques

- Retenção ingênua × Kaplan-Meier por safra, com M12, M18 e M24 vazios onde a safra não tem tempo de observação
- Log-rank por canal, plano e safra, com pares corrigidos por Holm ({{ comparacoes.safra.n_sig_bruto }} de {{ comparacoes.safra.n_pares }} pares entre safras significativos sem correção, {{ comparacoes.safra.n_sig_holm }} com Holm)
- Cox com violação de riscos proporcionais mostrada (Schoenfeld) e corrigida (estrato por plano, promoção por períodos), com tabela de efeito plantado × estimado ({{ cox.cobertura.corrigido|pct(0) }} dos IC 95% cobrem o valor plantado)
{% if recuperacao_mc is defined %}
- Validação em {{ recuperacao_mc.n_replicas|int }} réplicas de seed: IC 95% cobrindo o efeito plantado em {{ recuperacao_mc.cobertura_total|pct(0) }} dos casos
{% endif %}
- LTV de contribuição por canal contra um CAC incerto, com payback, IC por bootstrap, ponto de equilíbrio e realocação de verba como faixa de cenários
- Ponte de MRR, retenção líquida de receita (NRR {{ d.nrr.nrr|pct(0) }}), reativação, troca de plano e conversão de trial
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

O gerador usa numpy com semente {{ premissas.seed }} e parâmetros centralizados em um arquivo de configuração. A duração vem de um modelo de risco por partes (exponencial por intervalos) em grade diária, com o risco mensal-base de
{{ premissas.risco_mensal_base|pct }}. São {{ dados.n|int }} assinantes, {{ dados.pct_censurados|pct(0) }} deles censurados à direita no corte de {{ premissas.corte|data }}. Os efeitos plantados ficam gravados em um arquivo de verdade (`ground_truth.json`).

### Fonte única de números

Todo número do README, do relatório e deste texto é renderizado a partir de `results.json` por um template; um teste confere que nenhum número foi digitado à mão.

### Testes e verificação

A suíte pytest ({{ meta.n_testes|int }} testes) cobre determinismo da seed, invariantes de censura, Kaplan-Meier e log-rank contra exemplos calculados à mão e contra o lifelines, recuperação dos efeitos plantados (HR dentro da tolerância e IC cobrindo a verdade),
detecção da violação de riscos proporcionais, a ponte de MRR (fecha em todos os meses), a validação fora do tempo e a coerência entre `results.json` e os documentos. Há dois notebooks executáveis de ponta a ponta.

## Limites

Dados sintéticos não provam nada sobre uma empresa real, e os efeitos foram plantados: o projeto mostra que o método os recupera e quanto ele erra quando o gerador não espelha o modelo. O dataset público é dado de exemplo de outro setor.
O KM agregado mistura safras com riscos diferentes. ARPU, margem, CAC, taxa de desconto, a camada de operação (reativação, troca de plano, trial) e a efetividade da ação do mês 3 são premissas, e a realocação de verba depende do CAC marginal, mostrado como cenários.
Ficaram de fora modelos de fragilidade, efeitos que variam no tempo no dataset público, validação com dado de operação real e o efeito causal do reajuste.
