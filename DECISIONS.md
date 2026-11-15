# DECISIONS.md — Premissas e decisões

Este projeto foi construído de forma autônoma, sem supervisão interativa. Sempre que a especificação deixou
dúvida, escolhi a opção mais simples e a registrei aqui. Os números abaixo vêm de
[`results/results.json`](results/results.json) (gerado a partir de `src/sobrevivencia/config.py`).

## Ambiente técnico

- **Python 3.13 no venv.** O Python padrão da máquina de desenvolvimento era mais novo (Python 3.15) e as bibliotecas científicas
  ainda não tinham wheels para ele. Usei um venv a partir do Python 3.13 (versão efetiva: 3.13.17).
  O `lifelines` (0.30.3) instalou normalmente nessa versão, então **não foi necessário** usar o
  `scikit-survival`. Quem tiver Python 3.11–3.13 padrão pode usar `python -m venv .venv` direto.
- **Sem Makefile** (ambiente Windows/PowerShell): `run_all.py` é o ponto de entrada único; os comandos estão no README.
- **requirements.txt fixado** (`pip freeze` do venv; dependências exclusivas de Windows ganham marcador de plataforma).
- **Notebooks usam o kernel `python3`**, então executam com qualquer venv ativo (sem registrar kernel nomeado).

## Dados sintéticos (nada é real)

- **Seed 42**, 12.000 assinantes, entradas de 01/11/2024 a 31/10/2026, corte fixo em
  31/10/2026. Entradas seguem uma intensidade diária com picos nas campanhas (Black Friday 2024 e 2025, Passe Copa 2026, Eleições 2026).
- **Duração por modelo de risco por partes** (exponencial por intervalos): risco constante por dia dentro de cada mês de vida,
  risco mensal-base de referência 3,5% (plano mensal, canal orgânico, engajamento médio, mobile).
  A grade é diária para que o reajuste de preço (efeito de calendário) tenha corte exato.
- **Efeitos plantados** (razões de risco; a verdade fica em `results/ground_truth.json`):

| Efeito | Valor plantado |
|---|---:|
| Canal: Busca paga (vs orgânico) | 1,15 |
| Canal: Mídia paga (Meta) (vs orgânico) | 1,50 |
| Canal: Social (vs orgânico) | 1,20 |
| Canal: Indicação (vs orgânico) | 0,70 |
| Canal: E-mail/CRM (vs orgânico) | 0,85 |

| Efeito | Valor plantado |
|---|---:|
| Engajamento (+1 desvio-padrão) | 0,78 |
| Passe Copa | 1,60 |
| Reajuste de preço (Mensal/Combo, 01/07/2026 a 31/08/2026) | 1,50 |
| Promoção vigente (meses 0–3) | 0,85 |
| **Penhasco** (mês seguinte ao fim da promoção) | 3,00 |
| Pós-penhasco (meses 4–6) | 1,35 |
| Plano combo / estudante (vs mensal) | 0,75 / 1,20 |
| Dispositivo | efeito **nulo** de propósito (o método não deve "descobrir" nada) |

- **O penhasco viola os riscos proporcionais de propósito**: o efeito da promoção muda por período de vida.
- **Plano anual** cancela quase só na renovação (mês 12): risco pré-renovação muito baixo e pico no intervalo 12–13.
- **Causas** (voluntário, involuntário, fim de contrato) são atribuídas por sorteio *depois* de simular o tempo, com probabilidades que
  dependem da idade e do plano. Assim o risco total mantém o HR plantado e as causas servem à análise de riscos competitivos.
- **Passe Copa** não tem desconto de preço na parte de valor (premissa simplificadora). **Eleições 2026** só afetam a aquisição
  (volume e mix de canais), não o risco. **Reativações** foram ignoradas: um assinante cancelado não volta.

## Desenho (A)

- **Evento** = cancelamento efetivo da assinatura (fim do acesso pago). **Origem do tempo** = data da primeira cobrança.
  **Duração** em meses (1 mês = 30,4375 dias). **Censura à direita** = ainda ativo no corte; exposição mínima de 1 dia.
- **Safra** = trimestre de entrada contado a partir de 01/11/2024 (8 safras de 3 meses).

## Kaplan-Meier e observabilidade (B, C)

- KM com **IC 95% log-log (Greenwood)**, implementado em numpy e conferido contra `lifelines` e contra um exemplo calculado à mão.
- **Regra de "tem tempo de observação"**: uma estimativa em M12/M18/M24 só é publicada se houver pelo menos 30 assinantes sob
  risco no horizonte **e**, para uma safra, se **todos** os seus membros puderem ter sido observados até o horizonte. Resultado: M12 só nas
  safras S1–S4, M18 só em S1–S2 e **M24 em nenhuma** (célula vazia, nunca preenchida).
- **Metas fictícias editáveis**: M12 65%, M18 55%, M24 48% (`config.METAS`).
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

- **LTV descontado em 24 meses** = soma, por mensalidade (cobrança no início do mês), de ARPU × sobrevivência KM do canal × desconto
  (taxa 12% ao ano). ARPU = preço de tabela do plano (Mensal R$ 29,90, Combo R$ 44,90,
  Anual R$ 24,92 mensal-equivalente, Estudante R$ 14,90), com 60% de desconto nos
  3 primeiros meses para quem entrou pela Black Friday. Sem reajuste de preço e **sem margem de contribuição** (decisão pela simplicidade; o LTV é de receita).
- **Medido × projetado**: o LTV é "medido" enquanto há pelo menos 30 assinantes sob risco; além do suporte, extrapolo a cauda
  com risco constante (média dos últimos 6 meses do suporte). A decisão em R$ (realocação e ação do mês 3) é **sempre projetada**.
- **CAC por canal (premissa fictícia)**: Orgânico R$ 30; Busca paga R$ 95; Mídia paga (Meta) R$ 52; Social R$ 60; Indicação R$ 56; E-mail/CRM R$ 22.  Escolhi valores em que a mídia paga é o canal **pago** mais barato, para que a pergunta "CAC ou permanência?" tenha resposta não trivial.
  Orgânico e e-mail/CRM são canais próprios, de capacidade limitada, e **não entram na realocação de verba**.
- **IC por bootstrap de assinantes**: 1.000 réplicas, reamostrando dentro de cada canal.
- **Ação no mês 3 da promoção**: custo de R$ 4 por assinante tratado e efetividade-base de
  35% do excesso de cancelamentos (com cenários de 15%, 35%, 50%) são premissas minhas.
  O benefício considera só o excesso do mês do penhasco, não o pós-penhasco (conservador). O contrafactual sem penhasco assume risco proporcional dentro do período.
- **Realocação de verba**: exemplo de R$ 100.000; supõe que o CAC médio vale na margem (não vale: canais saturam).

## Armadilhas (F) e riscos competitivos (G)

- Ranking por M12 bruto: 1.000 sorteios de 300 assinantes entre os elegíveis (todos com 12 meses possíveis).
- **Riscos competitivos** (Aalen-Johansen, implementação própria conferida contra um exemplo à mão e contra a identidade CIF + S = 1) foram feitos **depois** que os
  testes das etapas A–F passaram: `run_all.py` roda a suíte de métodos antes de calcular a seção G (`--sem-gate` para pular).

## Documentos

- **Fonte única**: README, este arquivo, o relatório HTML e `portfolio/case.md` são renderizados por Jinja2 a partir de `results.json`.
  Os modelos em `templates/` não têm números digitados; um teste varre os modelos e confere a coerência com `results.json`.
- Fontes do relatório: pilha de sistema (sem CDN, sem Google Fonts), para abrir offline.

## O que não foi feito

Modelos de fragilidade ou de cura, reativações, upgrade/downgrade de plano, efeito causal do reajuste (apenas associação),
dependência entre canais, sazonalidade além dos efeitos plantados, validação fora da amostra.
