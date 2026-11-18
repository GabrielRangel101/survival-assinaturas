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

**1. A retenção medida é {{ ingenuo_vs_km.global.m12.valor|pct }} em M12 e {{ ingenuo_vs_km.global.m24.valor|pct }} em M24.**
Por Kaplan-Meier (e não "ativos ÷ iniciados"): M12 {{ ingenuo_vs_km.global.m12.valor|pct }} (IC {{ ingenuo_vs_km.global.m12.lo|pct }} a {{ ingenuo_vs_km.global.m12.hi|pct }}),
{{ d.status_txt[ingenuo_vs_km.global.m12.status] }} meta fictícia de {{ premissas.metas.m12|pct(0) }}; M18 {{ ingenuo_vs_km.global.m18.valor|pct }}
(IC {{ ingenuo_vs_km.global.m18.lo|pct }} a {{ ingenuo_vs_km.global.m18.hi|pct }}), {{ d.status_txt[ingenuo_vs_km.global.m18.status] }} meta de {{ premissas.metas.m18|pct(0) }};
M24 {{ ingenuo_vs_km.global.m24.valor|pct }} (IC {{ ingenuo_vs_km.global.m24.lo|pct }} a {{ ingenuo_vs_km.global.m24.hi|pct }}), {{ d.status_txt[ingenuo_vs_km.global.m24.status] }} meta de {{ premissas.metas.m24|pct(0) }}.
A conta ingênua por safra vai de {{ d.ingenua_pior.ret_ingenua|pct(0) }} a {{ d.ingenua_melhor.ret_ingenua|pct(0) }} e tem correlação {{ ingenuo_vs_km.rho_ingenua_idade|sn(2) }} com a idade da safra:
mede quando a safra entrou, não se ela retém.

**2. A retenção quebra no mês seguinte ao fim da promoção.** {{ acao_mes3.medido.q_penhasco|pct }} de quem chegou ao mês 3 da Black Friday cancela em um mês,
contra {{ armadilhas.riscos_proporcionais.q_base_mes3|pct }} de quem entrou sem promoção. O Cox ajustado estima risco **{{ d.pen.hr|hr }}×** maior (IC {{ d.pen.hr_lo|hr }} a {{ d.pen.hr_hi|hr }});
o Cox ingênuo, com um HR único, enxerga só {{ d.hr_bf.hr|hr }}× e esconde o penhasco.

**3. O canal mais barato não é o que mais rende, mas o ranking de retorno depende de uma premissa (o CAC).**
{{ d.canal_mais_barato.rotulo }} tem o menor CAC entre os canais com verba ({{ d.canal_mais_barato.cac|brl }}), mas a permanência põe {{ d.canal_melhor.rotulo }} na frente:
LTV de contribuição em {{ premissas.horizonte_ltv }} meses de {{ d.canal_melhor.ltv.est|brl }} (IC {{ d.canal_melhor.ltv.lo|brl }} a {{ d.canal_melhor.ltv.hi|brl }}) contra
{{ d.canal_midia.ltv.est|brl }} (IC {{ d.canal_midia.ltv.lo|brl }} a {{ d.canal_midia.ltv.hi|brl }}). O ranking só por permanência não usa o CAC:
{% for c in d.rank_ltv %}{{ c.rotulo }}{{ " > " if not loop.last else "." }}{% endfor %}{{ " " }}
Com o CAC variando {{ premissas.cac_incerteza|pct(0) }} para cima e para baixo, o retorno por real é de {{ d.canal_melhor.ltv_cac_incerteza.est|n(1) }}× em {{ d.canal_melhor.rotulo }}
(IC {{ d.canal_melhor.ltv_cac_incerteza.lo|n(1) }} a {{ d.canal_melhor.ltv_cac_incerteza.hi|n(1) }}) e {{ d.canal_midia.ltv_cac_incerteza.est|n(1) }}× em {{ d.canal_midia.rotulo }}
(IC {{ d.canal_midia.ltv_cac_incerteza.lo|n(1) }} a {{ d.canal_midia.ltv_cac_incerteza.hi|n(1) }}); {{ d.canal_melhor.rotulo }} é o melhor em {{ d.canal_melhor.prob_melhor_ltv_cac|pct(0) }} das réplicas.
Não é certeza: é uma vantagem moderada que some se o CAC de {{ d.canal_midia.rotulo }} cair {{ d.empate_midia.queda|pct(0) }} ({{ d.empate_midia.cac_empate|brl }}).

**Decisão (projeção, não medição).** Mover verba de {{ d.real_origem.rotulo }} para {{ d.real_destino.rotulo }} **em etapas**, enquanto o CAC marginal de {{ d.real_destino.rotulo }} ficar abaixo de
{{ d.real.premio_equilibrio|pct(0) }} acima do médio (ponto de equilíbrio; IC {{ d.real.premio_equilibrio_lo|pct(0) }} a {{ d.real.premio_equilibrio_hi|pct(0) }}).
Para cada {{ premissas.verba_exemplo|brl_mi }} movidos, o valor líquido é de {{ d.real.linhas[0].ganho|brl_mi }} (IC {{ d.real.linhas[0].lo|brl_mi }} a {{ d.real.linhas[0].hi|brl_mi }}) se o CAC marginal for igual ao médio
e de {{ d.real.linhas[2].ganho|brl_mi }} (IC {{ d.real.linhas[2].lo|brl_mi }} a {{ d.real.linhas[2].hi|brl_mi }}) se for {{ d.real.linhas[2].premio|pct(0) }} maior. A ação de retenção no mês 3 só se paga se evitar mais de
{{ acao_mes3.projetado.efetividade_equilibrio|pct(0) }} do excesso de cancelamentos, e **não deve ser escalada antes de um teste**: provar {{ d.teste.linhas[1].efetividade|pct(0) }} de efetividade exige
cerca de {{ d.teste.linhas[1].n_por_braco|int }} assinantes por braço, mais do que uma campanha de Black Friday inteira ({{ d.teste.vivos_mes3_coorte|int }} chegam ao mês 3).

## O que este projeto demonstra

- **A. Desenho**: evento (cancelamento efetivo), origem do tempo (primeira cobrança), corte fixo e censura à direita.
- **B. O erro clássico**: retenção ingênua por safra × Kaplan-Meier com IC 95% (log-log); metas editáveis; sem
  preencher M12/M18/M24 onde a safra não tem tempo de observação.
- **C. Comparações**: log-rank por canal, plano e safra; pares com correção de Holm.
- **D. Cox**: razões de risco com IC e C-index; teste de riscos proporcionais (Schoenfeld) que **mostra a violação**;
  correção (estratificação por plano + promoção por períodos + reajuste); tabela plantado × estimado.
- **E. Valor por canal**: RMST e LTV de **contribuição** (com margem) em {{ premissas.horizonte_ltv }} meses × CAC com incerteza, payback, IC por bootstrap e
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
| Assinantes sintéticos | {{ dados.n|int }} (seed {{ premissas.seed }}) |
| Entradas | {{ premissas.entrada_ini|data }} a {{ premissas.entrada_fim|data }} |
| Corte de observação | {{ premissas.corte|data }} |
| Cancelaram (evento) | {{ dados.n_eventos|int }} ({{ dados.pct_eventos|pct }}) |
| Censurados à direita (ainda ativos) | {{ dados.n_censurados|int }} ({{ dados.pct_censurados|pct }}) |
| Seguimento máximo possível | {{ dados.seguimento_max_meses|n(1) }} meses |
| Assinantes com ≥ 12 / ≥ 18 / ≥ 24 meses possíveis | {{ dados.n_com_12m_possiveis|int }} / {{ dados.n_com_18m_possiveis|int }} / {{ dados.n_com_24m_possiveis|int }} |

Causas observadas: voluntário {{ dados.causas.voluntario|int }}, involuntário (falha de pagamento) {{ dados.causas.involuntario|int }},
fim de contrato {{ dados.causas.fim_contrato|int }}.

A janela de entrada cobre {{ premissas.n_safras * premissas.meses_por_safra }} meses para que M24 seja **observável** nas safras mais antigas
(M24 vem preenchido em {{ ingenuo_vs_km.n_celulas_m24_preenchidas }} das {{ premissas.n_safras }} safras). Onde a safra não tem tempo de observação, a célula continua vazia.

### B. Ingênuo × Kaplan-Meier por safra

A "retenção ingênua" (ativos ÷ iniciados) só mede **há quanto tempo a safra entrou**: ela vai de
{{ d.ingenua_pior.ret_ingenua|pct(0) }} ({{ d.ingenua_pior.safra }}) a {{ d.ingenua_melhor.ret_ingenua|pct(0) }} ({{ d.ingenua_melhor.safra }})
e correlaciona {{ ingenuo_vs_km.rho_ingenua_idade|sn(2) }} (Spearman) com a idade da safra. O KM em M3, comparável entre safras,
tem correlação {{ ingenuo_vs_km.rho_km_m3_idade|sn(2) }} com a idade da safra: o que a conta ingênua mostra como "melhora" não é melhora.

| Safra | Entrada | n | Ingênua | KM M3 | KM M6 | KM M12 | KM M18 | KM M24 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
{% for l in ingenuo_vs_km.safras %}
| {{ l.safra }} | {{ premissas.rotulos.safra[l.safra] }} | {{ l.n|int }} | {{ l.ret_ingenua|pct(0) }} | {% for h in ["m3", "m6", "m12", "m18", "m24"] %}{% set p = l.horizontes[h] %}{{ (p.valor|pct(1)) if p.ok else "—" }}{{ " ▲" if p.status == "acima" else (" ▼" if p.status == "abaixo" else "") }} | {% endfor %}{{ "" }}
{% endfor %}

"—" = safra sem tempo de observação (não preenchida). ▲/▼ = IC 95% inteiro acima/abaixo da meta fictícia
(M12 {{ premissas.metas.m12|pct(0) }}, M18 {{ premissas.metas.m18|pct(0) }}, M24 {{ premissas.metas.m24|pct(0) }}; editáveis em `src/sobrevivencia/config.py`).

### C. Comparações (log-rank, Holm)

| Fator | χ² (gl) | p | Pares significativos (bruto → Holm) |
|---|---:|---:|---:|
| Canal | {{ comparacoes.canal.logrank.chi2|n(1) }} ({{ comparacoes.canal.logrank.df }}) | {{ comparacoes.canal.logrank.p|p }} | {{ comparacoes.canal.n_sig_bruto }} → {{ comparacoes.canal.n_sig_holm }} de {{ comparacoes.canal.n_pares }} |
| Plano | {{ comparacoes.plano.logrank.chi2|n(1) }} ({{ comparacoes.plano.logrank.df }}) | {{ comparacoes.plano.logrank.p|p }} | {{ comparacoes.plano.n_sig_bruto }} → {{ comparacoes.plano.n_sig_holm }} de {{ comparacoes.plano.n_pares }} |
| Safra | {{ comparacoes.safra.logrank.chi2|n(1) }} ({{ comparacoes.safra.logrank.df }}) | {{ comparacoes.safra.logrank.p|p }} | {{ comparacoes.safra.n_sig_bruto }} → {{ comparacoes.safra.n_sig_holm }} de {{ comparacoes.safra.n_pares }} |

Retenção KM em M12 por canal: {% for g in comparacoes.canal.grupos %}{{ g.rotulo }} {{ g.horizontes.m12.valor|pct(1) }}{{ "; " if not loop.last else "." }}{% endfor %}{{ "" }}


### D. Cox: plantado × estimado

O modelo **ingênuo** (riscos proporcionais, um HR por covariável) viola a premissa: o teste de Schoenfeld rejeita
{{ cox.ingenuo.n_viola }} de {{ cox.ingenuo.n_covs }} covariáveis (global p {{ cox.ingenuo.ph_global.p|p }}). O modelo **corrigido**
(estratificado por plano, promoção por períodos, reajuste como efeito de calendário) não é rejeitado
(global p {{ cox.corrigido.ph_global.p|p }}). C-index: {{ cox.ingenuo.cindex|n(3) }} (ingênuo) e {{ cox.corrigido.cindex_td|n(3) }}
(corrigido, só compara assinantes do mesmo plano).

| Efeito | Plantado | Cox ingênuo (IC 95%) | Cox corrigido (IC 95%) |
|---|---:|---:|---:|
{% for r in cox.plantado_vs_estimado %}
| {{ r.rotulo }} | {{ (r.verdade|hr) if r.verdade is not none else "—" }} | {% if r.ingenuo %}{{ r.ingenuo.hr|hr }} ({{ r.ingenuo.lo|hr }}–{{ r.ingenuo.hi|hr }}){% else %}—{% endif %} | {% if r.corrigido %}{{ r.corrigido.hr|hr }} ({{ r.corrigido.lo|hr }}–{{ r.corrigido.hi|hr }}){% elif r.complementar %}{{ r.complementar.hr|hr }} ({{ r.complementar.lo|hr }}–{{ r.complementar.hi|hr }})¹{% else %}—{% endif %} |
{% endfor %}

¹ HR de plano estimado num modelo complementar sem o plano anual (que é estratificado no modelo corrigido).
Cobertura dos IC 95% sobre os efeitos plantados: {{ cox.cobertura.corrigido|pct(0) }} no corrigido ({{ cox.cobertura.n_corrigido }} efeitos) contra
{{ cox.cobertura.ingenuo|pct(0) }} no ingênuo.

{% if recuperacao_mc is defined %}
**Validação em {{ recuperacao_mc.n_replicas|int }} réplicas** (seeds diferentes, mesmo gerador): o maior viés relativo médio entre os efeitos foi de
{{ recuperacao_mc.vies_abs_max|pct(1) }} e os IC 95% cobriram o valor plantado em {{ recuperacao_mc.cobertura_total|pct(0) }} dos
{{ recuperacao_mc.n_intervalos|int }} intervalos. Isso mostra que o resultado não depende da seed oficial, **não** que o modelo serve em dado real: o modelo corrigido
espelha a estrutura do gerador. As seções I e J tratam desse limite.
{% endif %}

### E. Valor por canal (RMST, LTV de contribuição, CAC, payback)

O LTV é de **contribuição**: receita ao preço de tabela vigente (com o reajuste de jul/2026) × sobrevivência × desconto de {{ premissas.taxa_desconto_anual|pct(0) }} ao ano ×
margem de {{ premissas.margem.por_real|pct(1) }} por real de receita ({{ premissas.margem.contribuicao|pct(0) }} de margem de contribuição menos {{ premissas.margem.cobranca|pct(1) }} de custo de cobrança).

| Canal | CAC (premissa) | RMST {{ premissas.horizonte_ltv }}m (meses) | LTV {{ premissas.horizonte_ltv }}m (R$) | % medido | LTV/CAC (IC: bootstrap + CAC incerto) | Payback (mensalidades) |
|---|---:|---:|---:|---:|---:|---:|
{% for c in valor.canais %}
| {{ c.rotulo }}{{ "" if c.escalavel else " *" }} | {{ c.cac|brl }} | {{ c.rmst.est|n(1) }} ({{ c.rmst.lo|n(1) }}–{{ c.rmst.hi|n(1) }}) | {{ c.ltv.est|brl }} ({{ c.ltv.lo|brl }}–{{ c.ltv.hi|brl }}) | {{ c.pct_ltv_medido|pct(0) }} | {% if c.escalavel %}{{ c.ltv_cac.est|n(1) }}× ({{ c.ltv_cac_incerteza.lo|n(1) }}–{{ c.ltv_cac_incerteza.hi|n(1) }}){% else %}n/c{% endif %} | {{ c.payback.est|n(0) }} |
{% endfor %}

\* canal próprio, de capacidade limitada e custo alocado: **o LTV/CAC não é comparável** com o dos canais pagos (n/c) e o canal não entra na realocação de verba.
IC 95% por bootstrap de assinantes ({{ valor.n_boot|int }} réplicas); no LTV/CAC o CAC também varia {{ premissas.cac_incerteza|pct(0) }} para cima e para baixo. **Medido** = parte do LTV coberta por Kaplan-Meier com pelo menos
{{ premissas.min_em_risco }} assinantes sob risco; o resto é projeção de cauda com risco constante. ARPU, margem, CAC e taxa de desconto são **premissas**
(os CACs foram escolhidos para que a pergunta "CAC ou permanência?" tivesse uma resposta não trivial; ver [`DECISIONS.md`](DECISIONS.md)).

**Realocação de verba como faixa (projeção).** Mover {{ premissas.verba_exemplo|brl_mi }} de {{ d.real_origem.rotulo }} para {{ d.real_destino.rotulo }}, conforme o CAC marginal de {{ d.real_destino.rotulo }} fique acima do médio:

| CAC marginal acima do médio | Valor líquido (estimativa) | IC 95% | Chance de ser positivo |
|---:|---:|---:|---:|
{% for l in d.real.linhas %}
| {{ l.premio|pct(0) }} | {{ l.ganho|brl_mi }} | {{ l.lo|brl_mi }} a {{ l.hi|brl_mi }} | {{ l.prob_positivo|pct(0) }} |
{% endfor %}

O ganho se anula quando o CAC marginal de {{ d.real_destino.rotulo }} chega a {{ d.real.premio_equilibrio|pct(0) }} acima do médio (IC {{ d.real.premio_equilibrio_lo|pct(0) }} a {{ d.real.premio_equilibrio_hi|pct(0) }}).

### F. O que poderia ter dado errado

1. **Censura ignorada**: na retenção M12 de toda a base (verdade plantada {{ armadilhas.censura.verdade|pct }}), tratar censurado como
   cancelado dá {{ d.metodos_censura.censura_como_cancelamento.valor|pct(0) }}, descartar os censurados dá
   {{ d.metodos_censura.descartar_censurados.valor|pct(0) }}; o KM dá {{ d.metodos_censura.kaplan_meier.valor|pct }}.
2. **Riscos proporcionais violados**: o HR único da promoção ({{ armadilhas.riscos_proporcionais.hr_unico_ingenuo|hr }}) prevê
   {{ armadilhas.riscos_proporcionais.q_previsto_ingenuo|pct }} de cancelamento no mês 3–4, mas o observado é
   {{ armadilhas.riscos_proporcionais.q_observado_bf_mes3|pct }} ({{ armadilhas.riscos_proporcionais.q_previsto_corrigido|pct }} no modelo corrigido).
3. **Ranking por M12 bruto com safra pequena**: com {{ armadilhas.ranking.tamanho_safra_pequena|int }} assinantes, o ranking bruto acerta o
   melhor canal em {{ armadilhas.ranking.p_acerta_melhor|pct(0) }} dos {{ armadilhas.ranking.n_sorteios|int }} sorteios e o pior em
   {{ armadilhas.ranking.p_acerta_pior|pct(0) }}.

### G. Riscos competitivos (Aalen-Johansen)

Até M18: voluntário {{ riscos_competitivos.pontos.m18.voluntario.est|pct }}, involuntário {{ riscos_competitivos.pontos.m18.involuntario.est|pct }},
fim de contrato (só anual) {{ riscos_competitivos.pontos.m18.fim_contrato.est|pct }}. "1 − KM tratando as outras causas como censura"
superestima o voluntário ({{ riscos_competitivos.pontos.m18.voluntario.um_menos_km|pct }} contra {{ riscos_competitivos.pontos.m18.voluntario.est|pct }} corretos).
O cancelamento involuntário (falha de pagamento) tem alavanca própria, que não é a da oferta: nova tentativa de cobrança e aviso antes do vencimento.

### H. Operação: MRR, retenção de receita, reativação, trial

A análise de sobrevivência olha o **primeiro** período de cada assinante. Esta camada (premissas fictícias de reativação, troca de plano e trial; fluxos aleatórios
independentes, então não muda a análise acima) mostra o que isso esconde. MRR de um assinante = preço pago no mês (com a promoção e o reajuste).

| Últimos 12 meses | R$ de MRR |
|---|---:|
| MRR no início | {{ operacao.ultimos_12m.inicial|brl }} |
| + Novos | {{ operacao.ultimos_12m.novo|brl }} |
| + Reativações | {{ operacao.ultimos_12m.reativacao|brl }} |
| + Upgrade de plano | {{ operacao.ultimos_12m.exp_upgrade|brl }} |
| + Fim da promoção (preço cheio) | {{ operacao.ultimos_12m.exp_fim_promo|brl }} |
| + Reajuste de preço | {{ operacao.ultimos_12m.exp_reajuste|brl }} |
| − Downgrade | {{ operacao.ultimos_12m.contracao|brl }} |
| − Churn | {{ operacao.ultimos_12m.churn|brl }} |
| **MRR no fim** | **{{ operacao.ultimos_12m.final|brl }}** (crescimento de {{ operacao.ultimos_12m.crescimento|pct(0) }}) |

- **Retenção líquida de receita (NRR) em {{ operacao.retencao_receita.global.n|int }} assinantes ativos em {{ operacao.retencao_receita.mes_base|mes_ano }}**: {{ d.nrr.nrr|pct(1) }} (IC {{ d.nrr.nrr_lo|pct(1) }} a {{ d.nrr.nrr_hi|pct(1) }});
  a retenção bruta (GRR, sem expansão) é {{ d.nrr.grr|pct(1) }}. A expansão (upgrade, fim de promoção e reajuste) recupera {{ d.nrr.expansao|pct(1) }} da receita da base, mas não o que o churn tirou.
- **Por canal (NRR)**: {% for c, v in d.nrr_canais %}{{ premissas.rotulos.canal[c] }} {{ v.nrr|pct(0) }}{{ "; " if not loop.last else "." }}{% endfor %}{{ "" }}
- **Reativação**: {{ operacao.reativacao.pct_cancelados_que_voltaram|pct(1) }} dos cancelamentos voltam; por causa (em até 12 meses): {% for k, v in operacao.reativacao.por_causa.items() %}{{ premissas.rotulos.causa[k] }} {{ v.taxa|pct(0) }}{{ "; " if not loop.last else "." }}{% endfor %}{{ "" }}
  Contando quem volta, a retenção em M12 sobe de {{ operacao.reativacao.retencao_m12_primeiro_periodo|pct(1) }} (só o primeiro período) para {{ operacao.reativacao.retencao_m12_com_reativacao|pct(1) }}.
- **Troca de plano**: {{ operacao.trocas_plano.pct_assinantes|pct(1) }} dos assinantes trocam de plano ({{ operacao.trocas_plano.n_trocas|int }} trocas).
- **Conversão de trial** (premissa): {{ operacao.trial.global.conversao|pct(1) }} no total; por canal: {% for t in d.trial_canais %}{{ t.rotulo }} {{ t.conversao|pct(0) }}{{ "; " if not loop.last else "." }}{% endfor %}{{ "" }}

### I. Quem tratar: fora do tempo, score e teste da ação

**Validação fora do tempo.** O modelo de score (Cox estratificado por plano) é ajustado só com o que se sabia em {{ d.fora.t0|data }} (seguimento truncado nessa data) e avaliado em
{{ d.fora.n_teste|int }} assinantes que entraram depois, cujo desfecho ele nunca viu e cujo período traz o reajuste de preço, o Passe Copa e as eleições, que o modelo não conhecia.

- C-index em {{ d.fora.horizonte }} meses: {{ d.fora.cindex.treino|n(3) }} no treino e **{{ d.fora.cindex.teste|n(3) }} no teste**. O **teto** (C-index do risco individual verdadeiro, que só existe porque os dados são sintéticos) é {{ d.fora.cindex.teto_verdadeiro|n(3) }}:
  nenhum modelo faria muito melhor, porque o tempo de vida tem muito acaso. Um C-index moderado é, neste caso, o esperado.
- O quinto de maior risco concentra {{ d.fora.captura.captura|pct(0) }} dos cancelamentos em {{ d.fora.horizonte }} meses (lift {{ d.fora.captura.lift|n(2) }}×).
- **Calibração**: o modelo **subestima** o cancelamento no teste ({% for a in d.fora.agregado %}M{{ a.h }}: previsto {{ a.previsto|pct(1) }}, observado {{ a.observado|pct(1) }}{{ "; " if not loop.last else "" }}{% endfor %}),
  porque não conhecia o reajuste de preço. O ranking de risco se mantém; os níveis exigem reajuste periódico do modelo.
- O score de cada assinante (probabilidade de cancelar em {{ d.fora.horizonte }} meses e decil) é gravado em `data/score_risco.csv` por `run_all.py`.

**Quem tratar no mês 3.** Entre os {{ d.alvo.n_bf_mes3|int }} assinantes da Black Friday que chegam ao mês 3, o excesso de cancelamento atribuível ao penhasco é maior no terço de maior risco:

| Terço de risco | n | Cancela no mês 3–4 | Efetividade de equilíbrio |
|---|---:|---:|---:|
{% for f in d.alvo.faixas %}
| {{ f.faixa }} | {{ f.n|int }} | {{ f.q_observado|pct(1) }} | {{ f.efetividade_equilibrio|pct(0) }} |
{% endfor %}

Tratar todos rende {{ d.alvo.liquido_tratar_todos|brl }} líquidos (projeção); tratar só o terço de maior risco, {{ d.alvo.liquido_tratar_maior_risco|brl }}. Com {{ d.alvo.efetividade_base|pct(0) }} de efetividade assumida, vale tratar todos; a priorização por risco só importa se a capacidade
de contato for limitada.

**Como provar que a ação funciona (teste A/B).** Desfecho primário: {{ d.teste.desfecho_primario }}. Randomização: {{ d.teste.randomizacao }}. Nível {{ d.teste.alpha|pct(0) }} e poder {{ d.teste.poder|pct(0) }}:

| Efetividade a detectar | Cancelamento no controle → tratamento | n por braço | Campanhas de Black Friday necessárias |
|---:|---:|---:|---:|
{% for l in d.teste.linhas %}
| {{ l.efetividade|pct(0) }} do excesso | {{ l.p_controle|pct(1) }} → {{ l.p_tratamento|pct(1) }} | {{ l.n_por_braco|int }} | {{ l.campanhas_necessarias|n(1) }} |
{% endfor %}

Com uma única campanha ({{ d.teste.vivos_mes3_coorte|int }} assinantes no mês 3) o teste só detectaria uma efetividade de {{ d.teste.efetividade_minima_detectavel|pct(0) }} do excesso. Conclusão prática: não dá para provar a ação numa Black Friday; é preciso
rodar o teste em **todas as saídas de promoção do ano**, ou aceitar um piloto com monitoramento e decisão por faixa de efetividade.

### J. Fora do roteiro: dataset público e gerador diferente

**Dataset público.** O mesmo pipeline roda numa amostra pública de churn de telecom publicada pela IBM (Apache-2.0; ver [`data_externo/LEIA-ME.md`](data_externo/LEIA-ME.md)), cujo processo gerador eu **não** plantei.
É dado de exemplo, não dado de operação, e é de telecom, não de jornal: os números abaixo não dizem nada sobre assinatura de notícias. {{ d.ext.dados.n|int }} clientes, {{ d.ext.dados.pct_eventos|pct(1) }} cancelaram.

- **O primeiro mês pesa muito**: {{ d.ext.primeiro_mes.pct_de_todos_cancelamentos|pct(0) }} de todos os cancelamentos acontecem no 1º mês de contrato (risco de {{ d.ext.primeiro_mes.taxa|pct(1) }} no mês), e {{ d.ext.primeiro_mes.taxa_contrato_mensal|pct(1) }} no contrato mensal.
- **Contrato**: retenção em M12 de {{ d.ext_contratos["Month-to-month"].horizontes.m12.valor|pct(1) }} no contrato mensal contra {{ d.ext_contratos["One year"].horizontes.m12.valor|pct(1) }} no de 1 ano e {{ d.ext_contratos["Two year"].horizontes.m12.valor|pct(1) }} no de 2 anos
  (log-rank p {{ d.ext.contrato.logrank.p|p }}; {{ d.ext.contrato.pares|selectattr("significativo_holm")|list|length }} de {{ d.ext.contrato.pares|length }} pares significativos com Holm). Boa parte disso é mecânica (contrato com fidelidade), não "comportamento".
- **Fibra óptica**: HR {{ d.ext_cor["internet_fibra"].hr|hr }} (IC {{ d.ext_cor["internet_fibra"].lo|hr }} a {{ d.ext_cor["internet_fibra"].hi|hr }}) contra DSL, no modelo estratificado por contrato; cheque eletrônico, HR {{ d.ext_cor["cheque_eletronico"].hr|hr }}.
  A cobrança mensal sai com HR {{ d.ext_cor["cobranca_z"].hr|hr }} (menor que 1), o que **não** significa que preço alto retém: ela é colinear com o tipo de internet, e o coeficiente só faz sentido junto com eles.
- **A correção que funcionou no sintético não resolve aqui**: estratificar por contrato não basta, e o teste de Schoenfeld ainda rejeita {{ d.ext.cox.corrigido.n_viola }} de {{ d.ext.cox.corrigido.n_covs }} covariáveis
  (global p {{ d.ext.cox.corrigido.ph_global.p|p }}). Com {{ d.ext.dados.n_eventos|int }} eventos o teste tem muito poder; o próximo passo seria efeitos que variam no tempo, não um HR único.
- **A definição do evento importa**: se a leitura fosse a de "tábua de período" (só quem cancelou no último mês), a retenção em M12 seria de {{ d.ext.leitura_periodo.m12|pct(1) }}, absurda para uma base com clientes de até {{ d.ext.dados.duracao_max|int }} meses.
  Só a leitura usual é coerente com o arquivo, mas a documentação do arquivo não resolve a dúvida.

**Gerador diferente do modelo.** O Cox corrigido espelha a estrutura do gerador oficial. Para ver o que acontece quando não espelha, o mesmo modelo foi ajustado em três tipos de dados
({{ robustez_mc.n_replicas|int }} réplicas de {{ robustez_mc.n|int }} assinantes cada): o gerador oficial (referência), um com heterogeneidade não observada entre assinantes e um com o penhasco fora do mês que o modelo supõe.

| Variante | Cobertura dos IC 95% | Maior viés relativo (efeito) |
|---|---:|---:|
{% for v in robustez_mc.variantes %}
| {{ v.descricao }} | {{ v.cobertura_total|pct(0) }} | {{ v.vies_abs_max|pct(0) }} ({{ d.rob_pior[v.id].rotulo }}) |
{% endfor %}

O modelo corrigido **depende de saber onde o penhasco está**: com o efeito fora do mês 3–4 que o modelo supõe, a cobertura cai para {{ d.rob.penhasco_deslocado.cobertura_total|pct(0) }} (contra {{ d.rob.oficial.cobertura_total|pct(0) }} na referência)
e o efeito mais distorcido é "{{ d.rob_pior.penhasco_deslocado.rotulo }}" ({{ d.rob_pior.penhasco_deslocado.media_hr|hr }} estimado contra {{ d.rob_pior.penhasco_deslocado.verdade|hr }} plantado).
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

Python {{ meta.versoes.python }}, pandas {{ meta.versoes.pandas }}, NumPy {{ meta.versoes.numpy }}, SciPy {{ meta.versoes.scipy }},
lifelines {{ meta.versoes.lifelines }}, statsmodels {{ meta.versoes.statsmodels }}, Matplotlib {{ meta.versoes.matplotlib }},
Jupyter, pytest. Reprodutível com a seed {{ premissas.seed }}.

## Feito com apoio de IA, sob minha direção

Este projeto foi construído por mim, Gabriel Rangel, **com apoio de IA (Claude), sob minha direção**: eu defini a pergunta de negócio, o desenho do
estudo, as premissas e os critérios de aceite; a IA escreveu e testou o código a partir dessas instruções. O histórico do Git mostra o Claude como coautor dos commits, de propósito.
Por isso existe o [`GUIA_DE_DEFESA.md`](GUIA_DE_DEFESA.md): cada escolha técnica está explicada para eu defendê-la sem consulta. Os dados são sintéticos e os resultados
não representam nenhuma empresa real.

Licença: MIT.
