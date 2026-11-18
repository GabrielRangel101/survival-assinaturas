# DECISIONS.md — Premissas e decisões

Este projeto foi construído de forma autônoma, sem supervisão interativa. Sempre que a especificação deixou
dúvida, escolhi a opção mais simples e a registrei aqui. Os números abaixo vêm de
[`results/results.json`](results/results.json) (gerado a partir de `src/sobrevivencia/config.py`).

A segunda rodada do projeto respondeu a uma revisão crítica externa (resultado circular, CAC escolhido para dar a história, LTV de receita,
falta de métricas de operação, M24 inobservável, nada sobre quem tratar, autoria). As decisões dessa rodada estão marcadas com **(revisão)**.

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
  {{ premissas.corte|data }}. Entradas seguem uma intensidade diária com picos nas campanhas (Black Friday de cada ano, Passe Copa 2026, Eleições 2026).
- **(revisão) Janela de entrada de {{ premissas.n_safras * premissas.meses_por_safra }} meses.** A primeira versão tinha 24 meses de entrada e 24 de seguimento, então a meta de M24
  nunca podia aparecer. Estendi as entradas para trás (mesmo corte), o que dá M24 observável nas safras mais antigas; o número de assinantes subiu para manter o volume mensal.
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
  (volume e mix de canais), não o risco. **Reativações** não entram no risco da análise de sobrevivência (que olha o primeiro período); a camada de operação as modela à parte (ver abaixo).

## Desenho (A)

- **Evento** = cancelamento efetivo da assinatura (fim do acesso pago). **Origem do tempo** = data da primeira cobrança.
  **Duração** em meses (1 mês = {{ premissas.dias_por_mes|n(4) }} dias). **Censura à direita** = ainda ativo no corte; exposição mínima de 1 dia.
- **Safra** = trimestre de entrada contado a partir de {{ premissas.entrada_ini|data }} ({{ premissas.n_safras }} safras de {{ premissas.meses_por_safra }} meses).

## Kaplan-Meier e observabilidade (B, C)

- KM com **IC 95% log-log (Greenwood)**, implementado em numpy e conferido contra `lifelines` e contra um exemplo calculado à mão.
- **Regra de "tem tempo de observação"**: uma estimativa em M12/M18/M24 só é publicada se houver pelo menos {{ premissas.min_em_risco }} assinantes sob
  risco no horizonte **e**, para uma safra, se **todos** os seus membros puderem ter sido observados até o horizonte. Resultado: M12 vem preenchido em {{ ingenuo_vs_km.n_celulas_m12_preenchidas }} safras, M18 em {{ ingenuo_vs_km.n_celulas_m18_preenchidas }} e
  M24 em {{ ingenuo_vs_km.n_celulas_m24_preenchidas }} de {{ premissas.n_safras }}; as demais ficam vazias, nunca preenchidas.
- **Metas fictícias editáveis**: M12 {{ premissas.metas.m12|pct(0) }}, M18 {{ premissas.metas.m18|pct(0) }}, M24 {{ premissas.metas.m24|pct(0) }} (`config.METAS`).
  O status compara o IC com a meta: "acima", "abaixo" ou "indistinguível".
- **Log-rank** multigrupo implementado em numpy (conferido com `lifelines`); pares com **correção de Holm** (`statsmodels`) dentro de cada família.

## Cox (D)

- **Ingênuo**: um HR por covariável (canal, plano, dispositivo, engajamento, Black Friday como efeito único, Passe Copa).
- **Corrigido**: estratificado por plano (absorve o pico do anual); promoção por **períodos de idade** (vigente, penhasco, pós-penhasco) e
  **reajuste como covariável de calendário**; ambos exigem dividir o tempo em episódios (`start`, `stop`] — estimativa equivalente à de covariáveis
  dependentes do tempo. Os HRs de plano (combo/estudante) saem de um **modelo complementar sem o anual**, pois o estrato absorve o plano.
- **Teste de Schoenfeld próprio** (escore de Grambsch-Therneau), porque o do `lifelines` não cobre estratos com entrada tardia. Dois testes:
  tendência em rank(t) (o "padrão", conferido com o `lifelines`) e **por faixas de idade**. {% if d.ph_i.oferta_bf.p_rank >= premissas.alpha / cox.ingenuo.n_covs %}O padrão **não detecta** o penhasco (o efeito sobe e
  depois desce, sem tendência linear); o teste por faixas detecta.{% else %}O padrão detecta o penhasco, mas com muito menos força (p {{ d.ph_i.oferta_bf.p_rank|p }}) do que o teste por faixas
  (p {{ d.ph_i.oferta_bf.p_faixas|p }}), porque o efeito sobe e depois desce, sem tendência linear (na primeira versão da janela de dados ele chegava a **não** detectar).{% endif %} Os dois aparecem no relatório.
- **C-index**: Harrell com covariáveis do instante do evento; no modelo estratificado compara só assinantes do mesmo plano (por isso não é diretamente comparável).

- **Validação em réplicas** (`montecarlo.py`): o Cox corrigido é reajustado em novos conjuntos sintéticos (seeds diferentes) para medir viés e cobertura
  fora da seed oficial; com `--rapido` o número de réplicas diminui.
- **(revisão) Robustez a um gerador diferente do modelo.** Recuperar 100% dos efeitos só mostra que o método funciona quando o modelo espelha o gerador.
  Por isso o mesmo Cox corrigido é ajustado também em dados com **heterogeneidade não observada** (fragilidade gama) e com o **penhasco deslocado** meio mês, e o relatório mostra o viés e a cobertura que sobram.

## Valor por canal (E)

- **(revisão) LTV de contribuição em {{ premissas.horizonte_ltv }} meses** = soma, por mensalidade (cobrança no início do mês), de ARPU × sobrevivência KM do canal × desconto
  (taxa {{ premissas.taxa_desconto_anual|pct(0) }} ao ano) × margem por real de receita ({{ premissas.margem.por_real|pct(1) }} = margem de contribuição de {{ premissas.margem.contribuicao|pct(0) }} menos
  {{ premissas.margem.cobranca|pct(1) }} de custo de cobrança; ambas são **premissas fictícias**). A primeira versão usava receita, o que inflava o LTV/CAC.
- **(revisão) ARPU = preço de tabela VIGENTE**, depois do reajuste de jul/2026 (Mensal {{ premissas.preco_vigente.mensal|brl(2) }}, Combo {{ premissas.preco_vigente.combo|brl(2) }},
  Anual {{ premissas.preco_vigente.anual|brl(2) }} mensal-equivalente, Estudante {{ premissas.preco_vigente.estudante|brl(2) }}), com {{ premissas.promo.desconto|pct(0) }} de desconto nos
  {{ premissas.promo.meses }} primeiros meses para quem entrou pela Black Friday. A pergunta é o valor de quem seria adquirido hoje.
- **Medido × projetado**: o LTV é "medido" enquanto há pelo menos {{ premissas.min_em_risco }} assinantes sob risco; além do suporte, extrapolo a cauda
  com risco constante (média dos últimos 6 meses do suporte). A decisão em R$ (realocação e ação do mês 3) é **sempre projetada**.
- **CAC por canal (premissa fictícia)**: {% for c, v in premissas.cac.items() %}{{ premissas.rotulos.canal[c] }} {{ v|brl }}{{ "; " if not loop.last else "." }}{% endfor %}{{ "" }}
  Escolhi valores em que a mídia paga é o canal **pago** mais barato, **para que a pergunta "CAC ou permanência?" tivesse resposta não trivial**. Isso deixa a conclusão de canal dependente de uma premissa, e por isso:
  **(revisão)** (1) o ranking só por permanência (LTV), que não usa o CAC, é mostrado à parte; (2) o CAC entra com incerteza de ±{{ premissas.cac_incerteza|pct(0) }} no bootstrap e a probabilidade de cada canal ser o melhor conta as duas incertezas;
  (3) o relatório mostra o CAC de empate (quanto o CAC do segundo colocado teria de mudar para virar o ranking).
  Orgânico e e-mail/CRM são canais próprios, de capacidade limitada e custo alocado: o **LTV/CAC deles não é comparável** com o dos pagos e aparece como "n/c"; eles **não entram na realocação de verba**.
- **IC por bootstrap de assinantes**: {{ premissas.n_boot|int }} réplicas, reamostrando dentro de cada canal.
- **Ação no mês 3 da promoção**: custo de {{ premissas.acao.custo_por_assinante|brl }} por assinante tratado e efetividade-base de
  {{ premissas.acao.efetividade_base|pct(0) }} do excesso de cancelamentos (com cenários de {% for e in premissas.acao.efetividades %}{{ e|pct(0) }}{{ ", " if not loop.last else "" }}{% endfor %}) são premissas minhas.
  O benefício é o valor de contribuição do assinante retido e considera só o excesso do mês do penhasco, não o pós-penhasco (conservador). O contrafactual sem penhasco assume risco proporcional dentro do período.
- **(revisão) Realocação de verba como faixa, não como número único.** O exemplo é de {{ premissas.verba_exemplo|brl }}. O CAC médio não vale na margem (canais saturam), então o ganho é calculado para o CAC marginal do canal
  de destino igual ao médio e {% for q in premissas.premios_cac_marginal[1:] %}{{ q|pct(0) }}{{ ", " if not loop.last else "" }}{% endfor %} acima dele, com IC (bootstrap + CAC incerto) e o ponto de equilíbrio. O número único de ganho saiu do resumo.

## Operação: MRR, reativação, troca de plano e trial (H) **(revisão)**

- É uma camada **à parte**, gerada com fluxos aleatórios independentes (`SeedSequence.spawn`), para **não mudar** nenhum tempo de vida da análise de sobrevivência, que continua olhando o primeiro período.
- **Premissas fictícias**: probabilidade de reativação por causa ({% for k, v in operacao.premissas.reativa_prob.items() %}{{ premissas.rotulos.causa[k] }} {{ v|pct(0) }}{{ "; " if not loop.last else "." }}{% endfor %}),
  atraso médio até voltar, risco mensal de {{ operacao.premissas.reativa_risco_mensal|pct(0) }} depois de reativar, taxas de troca de plano e conversão de trial por canal (em `config.py`).
- **MRR** = preço pago no mês (com a promoção e o reajuste), no fim de cada mês; o plano anual conta pelo preço mensal-equivalente. A ponte decompõe a variação em novos, reativações, upgrade, fim da promoção, reajuste, downgrade e churn,
  e um teste confere que a soma fecha em todos os meses. Quem entra e sai entre dois fins de mês não aparece.
- **NRR/GRR** em {{ operacao.premissas.janela_nrr_meses }} meses sobre a base ativa {{ operacao.premissas.janela_nrr_meses }} meses antes do último mês observado, com IC por bootstrap de assinantes.
- **Trial**: os trials que não converteram não existem no dataset; são sorteados por uma binomial negativa a partir da conversão plantada, para que a conversão observada tenha IC (Wilson).

## Quem tratar (I) **(revisão)**

- **Fora do tempo**: o modelo de score (Cox estratificado por plano) é ajustado com o que se sabia em {{ preditivo.fora_do_tempo.t0|data }} e avaliado em quem entrou depois. O **teto** de C-index
  (risco individual verdadeiro, só conhecido porque os dados são sintéticos) mostra o quanto um C-index moderado é esperado.
- **Score por assinante**: probabilidade de cancelar em {{ preditivo.fora_do_tempo.horizonte }} meses e decil, gravado em `data/score_risco.csv` (não versionado).
- **Alvo e teste da ação do mês 3**: terços de risco entre quem chega ao mês 3 da Black Friday e desenho do teste A/B (n por braço e campanhas necessárias). Nada disso é efeito medido da ação.

## Dataset público (J) **(revisão)**

- Amostra pública de churn de telecom publicada pela IBM (Apache-2.0), versionada em `data_externo/` com origem, licença e SHA-256 conferido em cada execução. **É dado de exemplo de outro setor**, não dado de operação real,
  e não entra em nenhuma conclusão sobre a Gazeta Meridiano; serve para ver o pipeline em dados que eu não plantei.
- Convenção: `tenure` = duração em meses, `Churn = Yes` = evento. Como a documentação sugere que o cancelamento é "no último mês", calculo também a leitura de tábua de período e mostro que ela é incoerente com o arquivo.
- Os {{ externo.fonte.excluidos_tenure_zero|int }} clientes com tenure zero ficam de fora (ainda sem cobrança).

## Armadilhas (F) e riscos competitivos (G)

- Ranking por M12 bruto: {{ premissas.n_sorteios_ranking|int }} sorteios de {{ premissas.tamanho_safra_pequena|int }} assinantes entre os elegíveis (todos com 12 meses possíveis).
- **Riscos competitivos** (Aalen-Johansen, implementação própria conferida contra um exemplo à mão e contra a identidade CIF + S = 1) foram feitos **depois** que os
  testes das etapas A–F passaram: `run_all.py` roda a suíte de métodos antes de calcular a seção G (`--sem-gate` para pular).

## Documentos

- **Fonte única**: README, este arquivo, o relatório HTML e `portfolio/case.md` são renderizados por Jinja2 a partir de `results.json`.
  Os modelos em `templates/` não têm números digitados; um teste varre os modelos e confere a coerência com `results.json`.
- Fontes do relatório: pilha de sistema (sem CDN, sem Google Fonts), para abrir offline.

## O que não foi feito

Modelos de fragilidade ou de cura no modelo principal, múltiplas reativações, efeito de upgrade/downgrade sobre o risco, efeito causal do reajuste (apenas associação),
dependência entre canais, sazonalidade além dos efeitos plantados, efeitos que variam no tempo para o dataset público e validação com dado de operação real (que eu não tenho).
