# DECISIONS.md — Premissas e decisões

Este projeto foi construído de forma autônoma, sem supervisão interativa. Sempre que a especificação deixou
dúvida, escolhi a opção mais simples e a registrei aqui. Os números abaixo vêm de
[`results/results.json`](results/results.json) (gerado a partir de `src/sobrevivencia/config.py`).

## Ambiente técnico

- **Python 3.13 no venv.** O Python padrão da máquina de desenvolvimento era mais novo (Python 3.15) e as bibliotecas científicas
  ainda não tinham wheels para ele. Usei um venv a partir do Python 3.13 (versão efetiva: {{ meta.versoes.python }}).
  O `lifelines` ({{ meta.versoes.lifelines }}) instalou normalmente nessa versão, então **não foi necessário** usar o
  `scikit-survival`. Quem tiver Python 3.11–3.13 padrão pode usar `python -m venv .venv` direto.
- **Sem Makefile** (ambiente Windows/PowerShell): `run_all.py` é o ponto de entrada único; os comandos estão no README.
- **requirements.txt fixado** (`pip freeze` do venv; dependências exclusivas de Windows ganham marcador de plataforma).
- **Notebooks usam o kernel `python3`**, então executam com qualquer venv ativo (sem registrar kernel nomeado).

## Dados sintéticos (nada é real)

- **Seed {{ premissas.seed }}**, {{ premissas.n|int }} assinantes, entradas de {{ premissas.entrada_ini|data }} a {{ premissas.entrada_fim|data }}, corte fixo em
  {{ premissas.corte|data }}. Entradas seguem uma intensidade diária com picos nas campanhas (Black Friday 2024 e 2025, Passe Copa 2026, Eleições 2026).
- **Duração por modelo de risco por partes** (exponencial por intervalos): risco constante por dia dentro de cada mês de vida,
  risco mensal-base de referência {{ premissas.risco_mensal_base|pct }} (plano mensal, canal orgânico, engajamento médio, mobile).
  A grade é diária para que o reajuste de preço (efeito de calendário) tenha corte exato.
- **Efeitos plantados** (razões de risco; a verdade fica em `results/ground_truth.json`):

| Efeito | Valor plantado |
|---|---:|
{% for c, v in premissas.hr_plantado.canal.items() %}
| Canal: {{ premissas.rotulos.canal[c] }} (vs orgânico) | {{ v|hr }} |
{% endfor %}

| Efeito | Valor plantado |
|---|---:|
| Engajamento (+1 desvio-padrão) | {{ premissas.hr_plantado.engajamento_por_dp|hr }} |
| Passe Copa | {{ premissas.hr_plantado.passe_copa|hr }} |
| Reajuste de preço (Mensal/Combo, {{ premissas.reajuste.ini|data }} a {{ premissas.reajuste.fim|data }}) | {{ premissas.hr_plantado.reajuste|hr }} |
| Promoção vigente (meses 0–{{ premissas.promo.meses }}) | {{ premissas.hr_plantado.promo.promo_vigente|hr }} |
| **Penhasco** (mês seguinte ao fim da promoção) | {{ premissas.hr_plantado.promo.promo_penhasco|hr }} |
| Pós-penhasco (meses 4–6) | {{ premissas.hr_plantado.promo.promo_pos|hr }} |
| Plano combo / estudante (vs mensal) | {{ premissas.hr_plantado.plano.combo|hr }} / {{ premissas.hr_plantado.plano.estudante|hr }} |
| Dispositivo | efeito **nulo** de propósito (o método não deve "descobrir" nada) |

- **O penhasco viola os riscos proporcionais de propósito**: o efeito da promoção muda por período de vida.
- **Plano anual** cancela quase só na renovação (mês 12): risco pré-renovação muito baixo e pico no intervalo 12–13.
- **Causas** (voluntário, involuntário, fim de contrato) são atribuídas por sorteio *depois* de simular o tempo, com probabilidades que
  dependem da idade e do plano. Assim o risco total mantém o HR plantado e as causas servem à análise de riscos competitivos.
- **Passe Copa** não tem desconto de preço na parte de valor (premissa simplificadora). **Eleições 2026** só afetam a aquisição
  (volume e mix de canais), não o risco. **Reativações** foram ignoradas: um assinante cancelado não volta.

## Desenho (A)

- **Evento** = cancelamento efetivo da assinatura (fim do acesso pago). **Origem do tempo** = data da primeira cobrança.
  **Duração** em meses (1 mês = {{ premissas.dias_por_mes|n(4) }} dias). **Censura à direita** = ainda ativo no corte; exposição mínima de 1 dia.
- **Safra** = trimestre de entrada contado a partir de {{ premissas.entrada_ini|data }} ({{ premissas.n_safras }} safras de {{ premissas.meses_por_safra }} meses).

## Kaplan-Meier e observabilidade (B, C)

- KM com **IC 95% log-log (Greenwood)**, implementado em numpy e conferido contra `lifelines` e contra um exemplo calculado à mão.
- **Regra de "tem tempo de observação"**: uma estimativa em M12/M18/M24 só é publicada se houver pelo menos {{ premissas.min_em_risco }} assinantes sob
  risco no horizonte **e**, para uma safra, se **todos** os seus membros puderem ter sido observados até o horizonte. Resultado: M12 só nas
  safras S1–S4, M18 só em S1–S2 e **M24 em nenhuma** (célula vazia, nunca preenchida).
- **Metas fictícias editáveis**: M12 {{ premissas.metas.m12|pct(0) }}, M18 {{ premissas.metas.m18|pct(0) }}, M24 {{ premissas.metas.m24|pct(0) }} (`config.METAS`).
  O status compara o IC com a meta: "acima", "abaixo" ou "indistinguível".
- **Log-rank** multigrupo implementado em numpy (conferido com `lifelines`); pares com **correção de Holm** (`statsmodels`) dentro de cada família.

## Cox (D)

- **Ingênuo**: um HR por covariável (canal, plano, dispositivo, engajamento, Black Friday como efeito único, Passe Copa).
- **Corrigido**: estratificado por plano (absorve o pico do anual); promoção por **períodos de idade** (vigente, penhasco, pós-penhasco) e
  **reajuste como covariável de calendário**; ambos exigem dividir o tempo em episódios (`start`, `stop`] — estimativa equivalente à de covariáveis
  dependentes do tempo. Os HRs de plano (combo/estudante) saem de um **modelo complementar sem o anual**, pois o estrato absorve o plano.
- **Teste de Schoenfeld próprio** (escore de Grambsch-Therneau), porque o do `lifelines` não cobre estratos com entrada tardia. Dois testes:
  tendência em rank(t) (o "padrão", conferido com o `lifelines`) e **por faixas de idade**. O padrão **não detecta** o penhasco (o efeito sobe e
  depois desce, sem tendência linear); o teste por faixas detecta. Os dois aparecem no relatório.
- **C-index**: Harrell com covariáveis do instante do evento; no modelo estratificado compara só assinantes do mesmo plano (por isso não é diretamente comparável).

- **Validação em réplicas** (`montecarlo.py`): o Cox corrigido é reajustado em novos conjuntos sintéticos (seeds diferentes) para medir viés e cobertura
  fora da seed oficial; com `--rapido` o número de réplicas diminui.

## Valor por canal (E)

- **LTV descontado em {{ premissas.horizonte_ltv }} meses** = soma, por mensalidade (cobrança no início do mês), de ARPU × sobrevivência KM do canal × desconto
  (taxa {{ premissas.taxa_desconto_anual|pct(0) }} ao ano). ARPU = preço de tabela do plano (Mensal {{ premissas.preco.mensal|brl(2) }}, Combo {{ premissas.preco.combo|brl(2) }},
  Anual {{ premissas.preco.anual|brl(2) }} mensal-equivalente, Estudante {{ premissas.preco.estudante|brl(2) }}), com {{ premissas.promo.desconto|pct(0) }} de desconto nos
  {{ premissas.promo.meses }} primeiros meses para quem entrou pela Black Friday. Sem reajuste de preço e **sem margem de contribuição** (decisão pela simplicidade; o LTV é de receita).
- **Medido × projetado**: o LTV é "medido" enquanto há pelo menos {{ premissas.min_em_risco }} assinantes sob risco; além do suporte, extrapolo a cauda
  com risco constante (média dos últimos 6 meses do suporte). A decisão em R$ (realocação e ação do mês 3) é **sempre projetada**.
- **CAC por canal (premissa fictícia)**: {% for c, v in premissas.cac.items() %}{{ premissas.rotulos.canal[c] }} {{ v|brl }}{{ "; " if not loop.last else "." }}{% endfor %}
  Escolhi valores em que a mídia paga é o canal **pago** mais barato, para que a pergunta "CAC ou permanência?" tenha resposta não trivial.
  Orgânico e e-mail/CRM são canais próprios, de capacidade limitada, e **não entram na realocação de verba**.
- **IC por bootstrap de assinantes**: {{ premissas.n_boot|int }} réplicas, reamostrando dentro de cada canal.
- **Ação no mês 3 da promoção**: custo de {{ premissas.acao.custo_por_assinante|brl }} por assinante tratado e efetividade-base de
  {{ premissas.acao.efetividade_base|pct(0) }} do excesso de cancelamentos (com cenários de {% for e in premissas.acao.efetividades %}{{ e|pct(0) }}{{ ", " if not loop.last else "" }}{% endfor %}) são premissas minhas.
  O benefício considera só o excesso do mês do penhasco, não o pós-penhasco (conservador). O contrafactual sem penhasco assume risco proporcional dentro do período.
- **Realocação de verba**: exemplo de {{ premissas.verba_exemplo|brl }}; supõe que o CAC médio vale na margem (não vale: canais saturam).

## Armadilhas (F) e riscos competitivos (G)

- Ranking por M12 bruto: {{ premissas.n_sorteios_ranking|int }} sorteios de {{ premissas.tamanho_safra_pequena|int }} assinantes entre os elegíveis (todos com 12 meses possíveis).
- **Riscos competitivos** (Aalen-Johansen, implementação própria conferida contra um exemplo à mão e contra a identidade CIF + S = 1) foram feitos **depois** que os
  testes das etapas A–F passaram: `run_all.py` roda a suíte de métodos antes de calcular a seção G (`--sem-gate` para pular).

## Documentos

- **Fonte única**: README, este arquivo, o relatório HTML e `portfolio/case.md` são renderizados por Jinja2 a partir de `results.json`.
  Os modelos em `templates/` não têm números digitados; um teste varre os modelos e confere a coerência com `results.json`.
- Fontes do relatório: pilha de sistema (sem CDN, sem Google Fonts), para abrir offline.

## O que não foi feito

Modelos de fragilidade ou de cura, reativações, upgrade/downgrade de plano, efeito causal do reajuste (apenas associação),
dependência entre canais, sazonalidade além dos efeitos plantados, validação fora da amostra.
