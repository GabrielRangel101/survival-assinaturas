# Dataset público usado na validação externa

| | |
|---|---|
| Arquivo | `telco_churn_ibm.csv` (7.043 linhas, 21 colunas) |
| Origem | https://github.com/IBM/telco-customer-churn-on-icp4d (arquivo `data/Telco-Customer-Churn.csv`) |
| Publicador | IBM, como dado de exemplo de uma operadora de telecom |
| Licença do repositório de origem | Apache-2.0 |
| SHA-256 | `16320c9c1ec72448db59aa0a26a0b95401046bef5d02fd3aeb906448e3055e91` |
| Obtido em | 18/11/2026 |

O arquivo está aqui sem nenhuma alteração, para o projeto rodar sem internet (`src/sobrevivencia/externo.py` confere o SHA-256).

**O que é e o que não é.** É um conjunto público de churn com a duração do cliente em meses (`tenure`) e o cancelamento (`Churn`),
**cujo processo gerador não fui eu quem desenhou**. Serve para testar se o pipeline se comporta em dados que eu não plantei.
Mas a própria IBM o distribui como dado de exemplo, então ele **não é um dado de operação real**, e é de telecom, não de assinatura de jornal.
Os resultados dele não entram em nenhuma conclusão sobre a Gazeta Meridiano.
