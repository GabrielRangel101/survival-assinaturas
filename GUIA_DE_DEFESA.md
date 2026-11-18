# Guia de defesa técnica — como eu explico cada escolha

Este projeto foi feito **com apoio de IA (Claude), sob minha direção**, e isso está declarado no README e nos commits. O que importa numa conversa técnica é eu conseguir explicar e defender
cada escolha sem consulta. Este guia é o meu roteiro: cada pergunta tem a **resposta curta**, o **porquê** e **onde está no código**. Os números vêm de `results/results.json`.

## 1. Por que Kaplan-Meier e não "ativos ÷ iniciados"?

**Resposta curta.** Porque "ativos ÷ iniciados" depende de há quanto tempo a safra entrou, não de quão bem ela retém. Aqui a correlação dela com a idade da safra é −0,98.

**Por quê.** O Kaplan-Meier estima S(t) = ∏ (1 − d_i / n_i) sobre os tempos de evento: em cada instante, a fração que cancela entre quem **ainda estava sob risco**. Quem ainda é assinante (censurado à direita) entra no risco até o último instante
em que foi observado e sai dele sem contar como cancelamento. Tratar censurado como cancelado, ou descartá-lo, joga fora justamente quem está permanecendo (seção F do relatório: erro de até 25 p.p. em M12).

**Onde.** `km.py` (`km_curve`); `tests/test_km_logrank.py` confere contra um exemplo calculado à mão e contra o `lifelines`.

## 2. Por que IC log-log e o que é a variância de Greenwood?

**Resposta curta.** Greenwood dá a variância de S(t); o IC log-log garante que o intervalo fica dentro de 0 a 1 e cobre melhor nas caudas.

**Por quê.** A variância de Greenwood é S(t)² · Σ d_i / (n_i (n_i − d_i)). Um IC simétrico em S(t) pode passar de 100% ou ficar abaixo de zero. Construir o intervalo para log(−log S(t)) e voltar à escala original
(S(t) elevado a exp(± z · σ), com σ = √(Σ d_i / (n_i (n_i − d_i))) / |log S(t)|) mantém o intervalo válido.

**Onde.** `km.py` (`km_ponto`) e `figures.py` (`_ic_curva`).

## 3. Por que "mínimo de 30 sob risco" e "safra com tempo de observação"?

**Resposta curta.** Para nunca publicar uma estimativa que o dado não sustenta.

**Por quê.** Com poucos assinantes sob risco o KM oscila e o IC explode; e uma safra só "tem" M24 se **todos** os seus membros puderam ser observados por 24 meses. Por isso a célula fica vazia em vez de preenchida:
M24 vem preenchido em 4 de 12 safras. Na primeira versão a janela de entrada era curta demais e M24 nunca aparecia; estendi as entradas para trás.

**Onde.** `cohorts.py` (`ponto`); `tests/test_cohorts.py`.

## 4. O que o log-rank testa e por que corrigir com Holm?

**Resposta curta.** O log-rank compara as curvas inteiras; Holm controla o erro de testar muitos pares.

**Por quê.** Em cada tempo de evento, compara os eventos observados com os esperados se os grupos tivessem o mesmo risco, e soma as diferenças (estatística qui-quadrado com k − 1 graus de liberdade). Tem mais poder quando as razões de risco são
proporcionais e perde poder quando as curvas se cruzam (o plano anual contra o mensal é um exemplo). Com 66 pares de safras, 25 parecem diferentes sem correção e 13 depois de Holm.
Holm é um Bonferroni em degraus: ordena os p-valores, compara o menor com α/m, o seguinte com α/(m − 1) e assim por diante, parando no primeiro que falha. Controla a taxa de erro por família e é sempre pelo menos tão poderoso quanto o Bonferroni, sem exigir independência.

**Onde.** `km.py` (`logrank`, `logrank_pares_holm`).

## 5. O que o Cox assume e como eu verifiquei?

**Resposta curta.** Que a razão de risco de cada covariável é constante no tempo. Eu testei com resíduos de Schoenfeld e a premissa **falha** no modelo ingênuo (de propósito).

**Por quê.** h(t | x) = h₀(t) · exp(β'x): a linha de base h₀(t) fica livre e o HR = exp(β) é o mesmo em qualquer idade. A verossimilhança parcial (com Efron para empates) não precisa de h₀. O resíduo de Schoenfeld de cada evento é o valor
da covariável de quem cancelou menos a média ponderada de quem estava sob risco; se a premissa vale, ele não tem relação com o tempo.

**Onde.** `cox.py`; `tests/test_cox.py`.

## 6. Por que um teste de Schoenfeld próprio e por que "por faixas de idade"?

**Resposta curta.** O do `lifelines` não cobre estratos com entrada tardia, e o teste padrão (tendência em rank do tempo) é **fraco** para um efeito que sobe e depois desce: aqui ele pega o penhasco, mas com muito menos força que o teste por faixas.

**Por quê.** O teste padrão testa β(t) = β + θ · g(t) com g linear no rank do tempo. O penhasco da promoção é um pico em um mês e some depois: não tem tendência linear (p 0,001 no padrão), e o teste por faixas de idade,
que deixa o efeito mudar por faixa, é muito mais sensível (p < 0,001). Com uma amostra menor o padrão chegou a deixar o penhasco passar; com esta, ele detecta, e a diferença de força entre os dois é o ponto. Escrevi os dois e conferi o padrão contra o `lifelines`. A lição que levo: olhar o gráfico do HR local, não só o p-valor. Num dataset real
com muitos eventos o teste tem tanto poder que rejeita desvios pequenos, então olho o tamanho do desvio (seção J do relatório: 7 de 9 covariáveis rejeitadas mesmo depois da correção).

**Onde.** `cox.py` (`teste_ph`, `_escore`); `figures.py` (`fig_schoenfeld`).

## 7. Como eu corrigi a violação e por que o C-index do corrigido é menor?

**Resposta curta.** Estratifiquei por plano, separei o efeito da promoção por períodos de idade e tratei o reajuste como efeito de calendário. O C-index cai porque no modelo estratificado só se comparam assinantes do mesmo plano.

**Por quê.** Estratificar dá a cada plano a sua própria linha de base (absorve o pico do anual na renovação). Efeitos que mudam com a idade ou com a data exigem dividir o tempo de cada assinante em episódios (start, stop], o equivalente a covariáveis dependentes do tempo.
O C-index do corrigido é 0,622 contra 0,640 do ingênuo, mas não são comparáveis: o ingênuo ganha pontos só por separar planos.

**Onde.** `cox.py` (`episodios`, `ajustar_corrigido`, `concordancia_td`).

## 8. HR é probabilidade? O que significa "2,64×"?

**Resposta curta.** Não. É uma razão de **taxas** de risco no mês. A tradução em probabilidade é q = 1 − (1 − q₀)^HR: de 3,9% sem promoção para 10,5% observado.

**Por quê.** Um HR de 2,64 não quer dizer "2,64 vezes a probabilidade", e sim a taxa instantânea multiplicada por esse fator; para um intervalo curto e probabilidade pequena as duas ideias andam juntas, mas não valem para probabilidades grandes.

## 9. RMST, LTV e por que não a mediana?

**Resposta curta.** O RMST é a área sob a curva de sobrevivência até 24 meses: os meses esperados de assinatura nessa janela. Não precisa de riscos proporcionais e existe mesmo quando a mediana não existe.

**Por quê.** A mediana só existe se a curva cruzar a metade dentro da janela, o que não acontece em todo recorte; o RMST sempre existe e tem leitura direta em meses. O LTV de contribuição soma, por mensalidade, ARPU × S(m) × desconto × margem. A parte **medida** é a coberta
pelo KM com pelo menos 30 sob risco; a cauda é **projeção** com risco constante, e a parcela medida está em cada linha da tabela. O IC vem de bootstrap de assinantes dentro do canal.

**Onde.** `value.py` (`curva_mensal`, `avaliar`, `analise_valor`).

## 10. O CAC é fictício. Isso não invalida a conclusão de canal?

**Resposta curta.** Invalida qualquer conclusão **dependente** do CAC, e é por isso que eu mostro o que não depende: o ranking por permanência (LTV) e o ponto em que o ranking vira.

**Por quê.** Escolhi os CACs para a pergunta "CAC ou permanência?" ter resposta não trivial, e está escrito no `DECISIONS.md`. Para não vender uma conclusão que veio da premissa: (1) o ranking só por LTV não usa o CAC
(Indicação > Busca paga > Social > Mídia paga (Meta)); (2) o CAC varia 30% para cima e para baixo no bootstrap, e Indicação é o melhor em 71% das réplicas (não em todas);
(3) o CAC de Mídia paga (Meta) teria de cair 19% para empatar; (4) a realocação é uma faixa de cenários de CAC marginal, com ponto de equilíbrio em 96% acima do médio.
Com CAC real, eu refaria a conta com o dado da empresa.

## 11. Por que Aalen-Johansen e não "1 − KM por causa"?

**Resposta curta.** Porque quem cancela por uma causa deixa de estar sob risco das outras; "1 − KM" tratando as outras causas como censura **superestima**.

**Por quê.** A incidência acumulada de cada causa é F_k(t) = Σ S(t⁻) · d_k / n: usa a sobrevivência **total** no instante anterior. As causas somam o cancelamento total (a soma CIF + S = 1 é um teste). Em M18 o "1 − KM" do voluntário dá 38,9%
contra 36,6% corretos.

**Onde.** `competing.py`; `tests/test_pitfalls_competing.py`.

## 12. "Recuperar os efeitos plantados" não é circular? O que você fez a respeito?

**Resposta curta.** É circular **em parte**, e eu disse isso. Por isso o projeto tem quatro camadas que não dependem de o modelo espelhar o gerador.

**Por quê e o que mostra cada camada.**

1. **Réplicas de seed**: o IC cobre o plantado em 93% dos casos. Prova estabilidade, **não** utilidade em dado real.
2. **Fora do tempo**: o modelo treinado até 31/10/2025 e testado em quem entrou depois, com C-index 0,667 contra um teto de 0,675 (o risco verdadeiro). O modelo subestima o cancelamento porque não conhecia o reajuste de preço: é um limite honesto.
3. **Gerador diferente do modelo**: heterogeneidade não observada e penhasco deslocado. A cobertura cai de 90% para 78% quando o penhasco está fora do mês que o modelo supõe.
4. **Dataset público de churn** (amostra de telecom publicada pela IBM, Apache-2.0): o mesmo pipeline em dados que eu não plantei.

**O que continua sem prova.** Nada disso é dado de operação real, e o dataset público é de exemplo e de outro setor. A única validação que falta é com dados de uma empresa de assinaturas.

## 13. O que o dataset público mostrou?

**Resposta curta.** Que o pipeline roda, que o primeiro mês concentra 20% dos cancelamentos, que o contrato mensal retém 70% em M12 contra 100% no de 2 anos
(em parte mecânico) e que a correção que funcionou no sintético **não** resolve a violação de riscos proporcionais ali.

**Cuidados.** Fibra óptica tem HR 3,51, mas a cobrança mensal sai com HR 0,44: é colinearidade com o tipo de internet, não "preço alto retém".
E a definição do evento importa: com a leitura de "tábua de período" a retenção em M12 seria 0,1%, incoerente com o arquivo.

## 14. Por que o C-index é "só" 0,67? O modelo é ruim?

**Resposta curta.** Não: o teto, com o **risco verdadeiro** de cada assinante, é 0,68. O tempo de vida tem muito acaso, e nenhum modelo passa disso nesses dados.

**Como eu usaria o score.** O quinto de maior risco concentra 35% dos cancelamentos em 6 meses (lift 1,76×). Serve para priorizar contato quando a capacidade é limitada. Os níveis de probabilidade precisam de reajuste periódico.

## 15. Como eu provaria que a ação do mês 3 funciona?

**Resposta curta.** Com um teste randomizado, e **não numa Black Friday só**: faltaria poder.

**Por quê.** Desfecho: cancelar entre o mês 3 e o mês 4. Para detectar 35% do excesso, preciso de cerca de 2.671 assinantes por braço, mais do que os 587 que chegam ao mês 3 numa campanha.
Com uma campanha só dá para detectar 94% do excesso. A saída é rodar o teste em todas as saídas de promoção do ano, ou aceitar um piloto com decisão por faixa de efetividade.
Hoje a ação é **projeção**: só se paga acima de 22% de efetividade.

## 16. Por que não usar uma floresta de sobrevivência, um AFT ou um modelo de fragilidade?

**Resposta curta.** Porque a pergunta de negócio é de interpretação (HR, onde quebra, o que fazer), e o Cox estratificado com períodos responde isso. Uma floresta de sobrevivência ou um boosting ganharia em predição pura, mas esconderia o penhasco.

**Quando eu mudaria.** Se o objetivo fosse só o score de risco, testaria uma floresta e compararia o C-index fora do tempo contra o teto. Se a heterogeneidade não observada importasse, ajustaria fragilidade (o teste de robustez mostra o que ela faz com o Cox). Está na lista do que não foi feito.

## 17. E se a censura for informativa?

**Resposta curta.** Aqui a censura é administrativa (o corte de observação), então não é informativa por construção. Em dado real, quem some da base sem cancelar (mudança de cartão, falha de integração) violaria a premissa; eu checaria o processo de dados e faria uma análise de sensibilidade.

## 18. Roteiro de três minutos

1. O problema: a retenção "ingênua" mede a idade da safra, não a retenção.
2. O método: Kaplan-Meier com censura, comparações com Holm, Cox com a premissa **testada**.
3. O achado: o penhasco no mês seguinte à promoção, que o HR único esconde (2,64× contra 1,14×).
4. A decisão: o ranking de canal por permanência, com o CAC como premissa explícita e o ponto de equilíbrio da realocação.
5. A honestidade: dados sintéticos, plantados; validei fora do tempo, em um dataset público e com um gerador diferente, e mostro onde o método erra.
