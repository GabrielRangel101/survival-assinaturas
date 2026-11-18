"""Configuração central: TODOS os parâmetros e premissas do projeto vivem aqui.

Universo fictício: jornal digital "Gazeta Meridiano". Dados 100% sintéticos.
Nada neste arquivo vem de uma empresa real; planos, preços e eventos foram
inspirados no gerador do projeto irmão ``meridiano-subscriber-compass`` (sem depender dele).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

# --------------------------------------------------------------------------------------
# Caminhos (ancorados na raiz do repositório, robustos a qualquer cwd)
# --------------------------------------------------------------------------------------
RAIZ = Path(__file__).resolve().parents[2]
DATA_DIR = RAIZ / "data"
RESULTS_DIR = RAIZ / "results"
FIGURES_DIR = RAIZ / "reports" / "figures"
REPORT_DIR = RAIZ / "report"
PORTFOLIO_DIR = RAIZ / "portfolio"
TEMPLATES_DIR = RAIZ / "templates"
NOTEBOOKS_DIR = RAIZ / "notebooks"

RESULTS_JSON = RESULTS_DIR / "results.json"
GROUND_TRUTH_JSON = RESULTS_DIR / "ground_truth.json"
DATASET_CSV = DATA_DIR / "assinantes.csv"

# --------------------------------------------------------------------------------------
# Desenho do estudo
# --------------------------------------------------------------------------------------
SEED = 42
N_ASSINANTES = 18_000
ENTRADA_INI = date(2023, 11, 1)  # 36 meses de entrada: as safras mais antigas têm 24+ meses de seguimento
ENTRADA_FIM = date(2026, 10, 31)
CORTE = date(2026, 10, 31)  # corte de observação fixo (censura à direita)
DIAS_POR_MES = 30.4375  # 365,25 / 12
ALPHA = 0.05

# Horizontes de retenção avaliados e metas FICTÍCIAS (editáveis; não são metas reais)
HORIZONTES = (12, 18, 24)
METAS = {12: 0.65, 18: 0.55, 24: 0.48}

# Mínimo de assinantes sob risco no horizonte para publicar uma estimativa de KM
MIN_EM_RISCO = 30

# --------------------------------------------------------------------------------------
# Atributos de entrada
# --------------------------------------------------------------------------------------
CANAIS = ("organico", "busca_paga", "midia_paga", "social", "indicacao", "email_crm")
CANAIS_ROTULO = {
    "organico": "Orgânico",
    "busca_paga": "Busca paga",
    "midia_paga": "Mídia paga (Meta)",
    "social": "Social",
    "indicacao": "Indicação",
    "email_crm": "E-mail/CRM",
}
CANAL_REF = "organico"
CANAL_PESOS = {
    "organico": 0.30,
    "busca_paga": 0.18,
    "midia_paga": 0.20,
    "social": 0.12,
    "indicacao": 0.08,
    "email_crm": 0.12,
}

PLANOS = ("mensal", "anual", "combo", "estudante")
PLANOS_ROTULO = {
    "mensal": "Mensal",
    "anual": "Anual",
    "combo": "Combo Streaming",
    "estudante": "Estudante",
}
PLANO_REF = "mensal"
PLANO_PESOS = {"mensal": 0.46, "anual": 0.16, "combo": 0.20, "estudante": 0.18}
# Inclinações plano|canal (multiplicadores sobre PLANO_PESOS; depois renormaliza)
PLANO_TILT_CANAL = {
    "indicacao": {"anual": 1.6},
    "social": {"estudante": 1.7},
    "email_crm": {"combo": 1.4},
    "midia_paga": {"mensal": 1.15},
}

DISPOSITIVOS = ("mobile", "desktop", "tablet")
DISPOSITIVO_REF = "mobile"
DISPOSITIVO_PESOS = {"mobile": 0.62, "desktop": 0.30, "tablet": 0.08}

ENG_MEDIA = 50.0  # engajamento pré-assinatura (0-100)
ENG_DP = 15.0
ENG_DESLOCA_CANAL = {
    "organico": 4.0,
    "busca_paga": 0.0,
    "midia_paga": -6.0,
    "social": -3.0,
    "indicacao": 8.0,
    "email_crm": 10.0,
}

OFERTAS = ("nenhuma", "black_friday", "passe_copa")

# Preços de tabela, mensal-equivalente (R$) -- premissa fictícia; reajuste em jul/2026
PRECO = {"mensal": 29.90, "combo": 44.90, "anual": 24.92, "estudante": 14.90}
PRECO_REAJUSTADO = {"mensal": 33.50, "combo": 49.90}
PROMO_DESCONTO = 0.60  # Black Friday: 60% de desconto
PROMO_MESES = 3  # por 3 meses

# Campanhas / eventos de calendário (início, fim, multiplicador de intensidade de entrada)
CAMPANHAS = {
    "black_friday_2023": (date(2023, 11, 24), date(2023, 12, 4), 4.0),
    "black_friday_2024": (date(2024, 11, 22), date(2024, 12, 2), 5.0),
    "black_friday_2025": (date(2025, 11, 21), date(2025, 12, 1), 6.0),
    "passe_copa_2026": (date(2026, 6, 11), date(2026, 7, 19), 1.8),
    "eleicoes_2026": (date(2026, 8, 16), date(2026, 10, 31), 1.4),
}
# Tendência de crescimento da intensidade diária de entrada (por mês)
CRESCIMENTO_MENSAL = 0.006
# Reajuste de preço (efeito sobre risco de Mensal e Combo no intervalo abaixo)
REAJUSTE_INI = date(2026, 7, 1)
REAJUSTE_FIM = date(2026, 8, 31)
REAJUSTE_PLANOS = ("mensal", "combo")

# Multiplicadores de canal nas campanhas (viés na composição de canais)
CANAL_TILT_CAMPANHA = {
    "black_friday": {
        "midia_paga": 2.2, "busca_paga": 1.3, "email_crm": 1.5,
        "organico": 0.8, "indicacao": 0.6, "social": 1.0,
    },
    "passe_copa": {"social": 1.8, "organico": 1.2, "midia_paga": 1.3},
    "eleicoes": {"organico": 1.5, "social": 1.5},
}
P_OFERTA_BF = 0.85  # prob. de aderir à promoção dentro da janela (planos não anuais)
P_OFERTA_COPA = 0.50  # idem para o Passe Copa

# --------------------------------------------------------------------------------------
# Modelo de risco por partes (VERDADE PLANTADA)
# Risco mensal (taxa) = HAZARD_BASE * forma_tenure(k) * HR_cov * efeitos_de_periodo.
# --------------------------------------------------------------------------------------
HAZARD_BASE = 0.035  # risco mensal-base (referência: mensal, orgânico, engaj. médio, mobile)

HR_CANAL = {
    "organico": 1.00,
    "busca_paga": 1.15,
    "midia_paga": 1.50,
    "social": 1.20,
    "indicacao": 0.70,
    "email_crm": 0.85,
}
HR_PLANO = {"mensal": 1.00, "combo": 0.75, "estudante": 1.20}  # anual: ver abaixo
HR_DISPOSITIVO = {"mobile": 1.00, "desktop": 1.00, "tablet": 1.00}  # efeito NULO de propósito
HR_ENGAJ_POR_DP = 0.78  # por +1 desvio-padrão de engajamento (protetor)
HR_PASSE_COPA = 1.60  # Passe Copa pior em todo o tempo de vida
HR_REAJUSTE = 1.50  # Mensal/Combo durante a janela do reajuste

# Forma da duração para planos não anuais (multiplicador por mês de vida k = 0, 1, 2, ...)
FORMA_TENURE = {0: 1.35, 1: 1.20, 2: 1.10}  # k>=3 -> 1,0 ; k>=12 -> TENURE_LONGO
TENURE_LONGO = 0.85

# Promoção da Black Friday: efeito POR PERÍODO (viola riscos proporcionais de propósito).
# k = mês de vida (0 = primeiro mês). Penhasco = mês seguinte ao fim da promoção (k = 3).
HR_PROMO_PERIODOS = {
    "promo_vigente": {"k_ini": 0, "k_fim": 3, "hr": 0.85},   # [0, 3)
    "promo_penhasco": {"k_ini": 3, "k_fim": 4, "hr": 3.00},  # [3, 4)
    "promo_pos": {"k_ini": 4, "k_fim": 6, "hr": 1.35},       # [4, 6)
}

# Plano anual: baixo risco antes da renovação + pico na renovação (intervalo k = 12)
ANUAL_HR_PRE = 0.10          # risco pré-renovação relativo ao plano mensal
ANUAL_RENOVACAO_K = 12
ANUAL_TAXA_RENOVACAO = 0.45  # taxa mensal no intervalo da renovação (referência)

# Causas de cancelamento (atribuídas por sorteio; não alteram o risco total)
P_INVOL_BASE = 0.12          # fração involuntária (falha de pagamento), planos não anuais
P_INVOL_INICIO = 0.30        # nos 2 primeiros meses (cartão recusado, 1ª cobrança)
P_INVOL_PENHASCO = 0.03      # no penhasco o cancelamento é quase todo voluntário
P_INVOL_RENOVACAO = 0.10     # anual: renovação falha por pagamento
# fim de contrato = não renovou o anual (voluntário na renovação)

CAUSAS = ("voluntario", "involuntario", "fim_contrato")
CAUSAS_ROTULO = {
    "voluntario": "Voluntário",
    "involuntario": "Involuntário (falha de pagamento)",
    "fim_contrato": "Fim de contrato (anual não renovado)",
}

MESES_LATENTES = 26  # grade diária da simulação cobre esses meses de vida (>= 24)

# --------------------------------------------------------------------------------------
# Safras (trimestres a partir da data de início da janela)
# --------------------------------------------------------------------------------------
N_SAFRAS = 12
MESES_POR_SAFRA = 3

# --------------------------------------------------------------------------------------
# Inferência / modelos
# --------------------------------------------------------------------------------------
N_BOOT = 1000
N_BOOT_RAPIDO = 100  # usado em testes
Z95 = 1.959963984540054

# --------------------------------------------------------------------------------------
# Valor por canal: premissas FICTÍCIAS e editáveis
# --------------------------------------------------------------------------------------
CAC = {  # custo de aquisição por assinante (R$) -- premissa fictícia
    "organico": 30.0,      # custo editorial/SEO alocado
    "busca_paga": 95.0,
    "midia_paga": 52.0,    # o canal PAGO mais barato por assinante
    "social": 60.0,
    "indicacao": 56.0,     # bônus do programa de indicação
    "email_crm": 22.0,     # base própria
}
# Canais que recebem verba incremental (escaláveis). Orgânico e e-mail/CRM são canais próprios,
# de capacidade limitada: aparecem na tabela, mas não entram na realocação de verba.
CANAIS_ESCALAVEIS = ("busca_paga", "midia_paga", "social", "indicacao")
TAXA_DESCONTO_ANUAL = 0.12  # taxa de desconto anual para o LTV
HORIZONTE_LTV = 24  # meses
VERBA_EXEMPLO = 100_000.0  # R$ realocados no exemplo de decisão

# LTV de CONTRIBUIÇÃO (e não de receita): fração da receita que sobra depois dos custos variáveis.
MARGEM_CONTRIBUICAO = 0.70   # premissa fictícia: sobra após conteúdo licenciado, plataforma e atendimento
CUSTO_COBRANCA = 0.035       # premissa fictícia: taxa do meio de pagamento sobre a receita cobrada
MARGEM_POR_REAL = MARGEM_CONTRIBUICAO - CUSTO_COBRANCA  # contribuição por R$ de receita
# ARPU = preço de tabela VIGENTE (pós-reajuste de jul/2026) para quem seria adquirido hoje.
# Incerteza do CAC: o CAC verdadeiro varia uniformemente em ±CAC_INCERTEZA em torno da premissa.
CAC_INCERTEZA = 0.30
# CAC marginal acima do médio no canal que recebe a verba (indicação e mídia saturam): cenários.
PREMIOS_CAC_MARGINAL = (0.0, 0.25, 0.50, 1.00)

# Ação no mês 3 da promoção (premissas de PROJEÇÃO; não medidas)
ACAO_EFETIVIDADES = (0.15, 0.35, 0.50)  # fração do excesso de cancelamentos evitada
ACAO_EFETIVIDADE_BASE = 0.35
ACAO_CUSTO_POR_ASSINANTE = 4.0  # R$ por assinante tratado no mês 3 (oferta no app/e-mail)
ACAO_COORTE_REFERENCIA = "black_friday_2025"

# Armadilhas
N_SORTEIOS_RANKING = 1000
TAMANHO_SAFRA_PEQUENA = 300

# --------------------------------------------------------------------------------------
# Visual
# --------------------------------------------------------------------------------------
COR = {
    "tinta": "#1C1A15",
    "papel": "#F3EFE4",
    "meridiano": "#1F3A5F",
    "vermelho": "#8C1D1D",
    "verde": "#2F6846",
    "cinza": "#8A8572",
    "ouro": "#9A7B1E",
}
COR_CANAL = {
    "organico": "#1F3A5F",
    "busca_paga": "#9A7B1E",
    "midia_paga": "#8C1D1D",
    "social": "#6B4E8C",
    "indicacao": "#2F6846",
    "email_crm": "#3D8FA3",
}
COR_PLANO = {
    "mensal": "#1F3A5F",
    "anual": "#8C1D1D",
    "combo": "#2F6846",
    "estudante": "#9A7B1E",
}

# --------------------------------------------------------------------------------------
# Camada de OPERAÇÃO (MRR, reativação, troca de plano, trial): premissas FICTÍCIAS.
# Gerada com fluxos de números aleatórios independentes (SeedSequence), então NÃO altera os
# tempos de vida da análise de sobrevivência, que segue olhando o PRIMEIRO período de assinatura.
# --------------------------------------------------------------------------------------
# Conversão de trial pago por canal (fração dos trials iniciados que viram assinatura)
TRIAL_CONVERSAO = {"organico": 0.38, "busca_paga": 0.30, "midia_paga": 0.18, "social": 0.22,
                   "indicacao": 0.52, "email_crm": 0.45}
# Troca de plano durante a vida (taxa mensal constante; destino). Anual não troca.
MUDANCA_PLANO = {"mensal": ("combo", 0.010), "combo": ("mensal", 0.006), "estudante": ("mensal", 0.012)}
# Reativação: probabilidade de voltar após cancelar (por causa) e atraso médio em dias (exponencial)
REATIVA_PROB = {"voluntario": 0.07, "involuntario": 0.30, "fim_contrato": 0.10}
REATIVA_ATRASO_DIAS = {"voluntario": 90.0, "involuntario": 15.0, "fim_contrato": 45.0}
REATIVA_RISCO_MENSAL = 0.05   # risco mensal constante de cancelar de novo após reativar
JANELA_NRR_MESES = 12
N_BOOT_OPERACAO = 400
