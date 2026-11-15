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

**Retenção medida (Kaplan-Meier, não "ativos ÷ iniciados").** Em M12, {{ ingenuo_vs_km.global.m12.valor|pct }}
(IC 95% {{ ingenuo_vs_km.global.m12.lo|pct }} a {{ ingenuo_vs_km.global.m12.hi|pct }}), {{ d.status_txt[ingenuo_vs_km.global.m12.status] }}
meta fictícia de {{ premissas.metas.m12|pct(0) }}. Em M18, {{ ingenuo_vs_km.global.m18.valor|pct }}
(IC {{ ingenuo_vs_km.global.m18.lo|pct }} a {{ ingenuo_vs_km.global.m18.hi|pct }}), {{ d.status_txt[ingenuo_vs_km.global.m18.status] }} meta de {{ premissas.metas.m18|pct(0) }}.
**M24 não é observável**: com entradas até o corte de {{ premissas.corte|data }}, ninguém tem 24 meses completos
({{ dados.n_com_24m_possiveis|int }} assinantes), então a célula fica vazia em vez de preenchida com um número inventado.

**Onde a retenção quebra.** No mês seguinte ao fim da promoção da Black Friday ({{ premissas.promo.desconto|pct(0) }} de desconto por
{{ premissas.promo.meses }} meses), {{ acao_mes3.medido.q_penhasco|pct }} de quem chegou ao mês 3 cancela em apenas um mês, contra
{{ armadilhas.riscos_proporcionais.q_base_mes3|pct }} de quem entrou sem promoção. O Cox ajustado estima um risco
**{{ d.pen.hr|hr }}×** maior nesse mês (IC 95% {{ d.pen.hr_lo|hr }} a {{ d.pen.hr_hi|hr }}); o Cox ingênuo, com um HR único para a
promoção, enxerga só {{ d.hr_bf.hr|hr }}× e **subestima o penhasco**.

**Qual canal vale a verba.** {{ d.canal_mais_barato.rotulo }} é o canal pago mais barato por assinante
({{ d.canal_mais_barato.cac|brl }}), mas {{ "a permanência inverte o ranking" if d.inverte else "o ranking se mantém" }}: o LTV descontado em
{{ premissas.horizonte_ltv }} meses de {{ d.canal_melhor.rotulo }} é {{ d.canal_melhor.ltv.est|brl }} contra
{{ d.canal_midia.ltv.est|brl }} de {{ d.canal_midia.rotulo }}, e o retorno por real investido é de
{{ d.canal_melhor.ltv_cac.est|n(1) }}× contra {{ d.canal_midia.ltv_cac.est|n(1) }}×. **{{ d.canal_pior.rotulo }}** é o pior retorno entre os
canais com verba ({{ d.canal_pior.ltv_cac.est|n(1) }}×).

**Decisão (projeção sobre premissas explícitas, não medição).**
Mover R$ {{ premissas.verba_exemplo|int }} de {{ d.canal_pior.rotulo }} para {{ d.canal_melhor.rotulo }} adiciona
cerca de {{ decisao_verba.ganho_realocar_pior_para_melhor|brl_mi }} de valor líquido (LTV − CAC), supondo que o CAC médio valha
na margem. No mês 3 da promoção, uma ação de retenção de {{ acao_mes3.projetado.custo_por_assinante|brl }} por assinante
tratado rende {{ acao_mes3.projetado.base.liquido|brl }} líquidos por coorte de referência (efetividade assumida de
{{ acao_mes3.projetado.efetividade_base|pct(0) }}) e só se paga se evitar mais de
{{ acao_mes3.projetado.efetividade_equilibrio|pct(0) }} do excesso de cancelamentos.

## O que este projeto demonstra

- **A. Desenho**: evento (cancelamento efetivo), origem do tempo (primeira cobrança), corte fixo e censura à direita.
- **B. O erro clássico**: retenção ingênua por safra × Kaplan-Meier com IC 95% (log-log); metas editáveis; sem
  preencher M12/M18/M24 onde a safra não tem tempo de observação.
- **C. Comparações**: log-rank por canal, plano e safra; pares com correção de Holm.
- **D. Cox**: razões de risco com IC e C-index; teste de riscos proporcionais (Schoenfeld) que **mostra a violação**;
  correção (estratificação por plano + promoção por períodos + reajuste); tabela plantado × estimado.
- **E. Valor por canal**: RMST e LTV descontado em {{ premissas.horizonte_ltv }} meses × CAC, payback e IC por bootstrap de
  assinantes, separando **medido** de **projetado**.
- **F. O que poderia ter dado errado**: censura ignorada, riscos proporcionais violados, ranking por M12 bruto com safra pequena.
- **G. Riscos competitivos**: incidência acumulada voluntário × involuntário × fim de contrato (Aalen-Johansen).
- **H. Limites honestos** (abaixo).

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

### B. Ingênuo × Kaplan-Meier por safra

A "retenção ingênua" (ativos ÷ iniciados) só mede **há quanto tempo a safra entrou**: ela vai de
{{ d.ingenua_pior.ret_ingenua|pct(0) }} ({{ d.ingenua_pior.safra }}) a {{ d.ingenua_melhor.ret_ingenua|pct(0) }} ({{ d.ingenua_melhor.safra }})
e correlaciona {{ ingenuo_vs_km.rho_ingenua_idade|sn(2) }} (Spearman) com a idade da safra. O KM em M3, comparável entre safras,
conta a história oposta (correlação {{ ingenuo_vs_km.rho_km_m3_idade|sn(2) }}: as safras recentes retêm um pouco **pior**).

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

Retenção KM em M12 por canal: {% for g in comparacoes.canal.grupos %}{{ g.rotulo }} {{ g.horizontes.m12.valor|pct(1) }}{{ "; " if not loop.last else "." }}{% endfor %}


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
{{ recuperacao_mc.n_intervalos|int }} intervalos, ou seja, o resultado acima não depende da seed oficial.
{% endif %}

### E. Valor por canal (RMST, LTV descontado, CAC, payback)

| Canal | CAC (premissa) | RMST {{ premissas.horizonte_ltv }}m (meses) | LTV {{ premissas.horizonte_ltv }}m (R$) | % medido | LTV/CAC | Payback (mensalidades) |
|---|---:|---:|---:|---:|---:|---:|
{% for c in valor.canais %}
| {{ c.rotulo }}{{ "" if c.escalavel else " *" }} | {{ c.cac|brl }} | {{ c.rmst.est|n(1) }} ({{ c.rmst.lo|n(1) }}–{{ c.rmst.hi|n(1) }}) | {{ c.ltv.est|brl }} ({{ c.ltv.lo|brl }}–{{ c.ltv.hi|brl }}) | {{ c.pct_ltv_medido|pct(0) }} | {{ c.ltv_cac.est|n(1) }}× ({{ c.ltv_cac.lo|n(1) }}–{{ c.ltv_cac.hi|n(1) }}) | {{ c.payback.est|n(0) }} |
{% endfor %}

\* canal próprio, de capacidade limitada: não entra na realocação de verba. IC 95% por bootstrap de assinantes
({{ valor.n_boot|int }} réplicas). **Medido** = parte do LTV coberta por Kaplan-Meier com pelo menos
{{ premissas.min_em_risco }} assinantes sob risco; o resto é projeção de cauda com risco constante. ARPU, CAC e taxa de desconto
({{ premissas.taxa_desconto_anual|pct(0) }} ao ano) são **premissas**.

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

Python {{ meta.versoes.python }}, pandas {{ meta.versoes.pandas }}, NumPy {{ meta.versoes.numpy }}, SciPy {{ meta.versoes.scipy }},
lifelines {{ meta.versoes.lifelines }}, statsmodels {{ meta.versoes.statsmodels }}, Matplotlib {{ meta.versoes.matplotlib }},
Jupyter, pytest. Reprodutível com a seed {{ premissas.seed }}.

## Feito com apoio de IA, sob minha direção

Este projeto foi construído por mim, Gabriel Rangel, **com apoio de IA (Claude), sob minha direção**: eu defini a pergunta de negócio, o desenho do
estudo, as premissas e os critérios de aceite; a IA escreveu e testou o código a partir dessas instruções. Os dados são sintéticos e os resultados
não representam nenhuma empresa real.

Licença: MIT.
