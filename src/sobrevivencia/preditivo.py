"""Quem está em risco e quem tratar: validação FORA DO TEMPO, score de risco por assinante, alvo da ação
do mês 3 e desenho do teste A/B da ação.

Validação fora do tempo (backtest "como se fosse em T0"): o modelo é ajustado só com o que se sabia em T0
(quem já tinha entrado, com o seguimento truncado em T0) e avaliado em quem entrou DEPOIS de T0, cujo
desfecho o modelo nunca viu. Isso tem de funcionar sem a ajuda do gerador: o período de teste traz o reajuste
de preço de jul/2026, o Passe Copa e as eleições, que o modelo treinado em T0 não conhecia.

Teto de desempenho: como os dados são sintéticos, o risco individual verdadeiro de cada assinante é conhecido.
O C-index desse risco verdadeiro (``teto``) é o melhor que QUALQUER modelo poderia obter nesses mesmos dados,
porque o tempo de vida tem muito acaso. Um C-index de 0,6 a 0,65 é, portanto, um resultado esperado, não uma falha.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
from lifelines import CoxPHFitter
from lifelines.utils import concordance_index
from statsmodels.stats.power import NormalIndPower
from statsmodels.stats.proportion import proportion_effectsize

from . import config as C
from . import cox as X
from . import km as K

T0 = date(2025, 10, 31)        # data "de hoje" do backtest (12 meses antes do corte)
H_SCORE = 6                    # horizonte do score: probabilidade de cancelar em até 6 meses
N_FAIXAS = 5                   # quintis de risco
COLS_SCORE = None              # preenchido por _covs()


def _covs(df: pd.DataFrame) -> pd.DataFrame:
    X_ = X.covariaveis_base(df, plano_dummies=False)
    X_["oferta_bf"] = (df["oferta_entrada"] == "black_friday").astype(float)
    return X_


def truncar_em(df: pd.DataFrame, t0: date) -> pd.DataFrame:
    """Visão do dataset 'como era em t0': só quem entrou até t0, com a duração e o evento truncados em t0."""
    d = df[df["data_inicio"] <= pd.Timestamp(t0)].copy()
    pot = ((pd.Timestamp(t0) - d["data_inicio"]).dt.days + 1) / C.DIAS_POR_MES
    ev = (d["evento"] == 1) & (d["duracao_meses"] < pot)
    d["duracao_meses"] = np.minimum(d["duracao_meses"], pot).clip(lower=1e-6)
    d["evento"] = ev.astype(int)
    d["seguimento_max_meses"] = pot
    return d


def ajustar_score(df: pd.DataFrame) -> CoxPHFitter:
    """Modelo de score: Cox estratificado por plano, com as covariáveis conhecidas na assinatura."""
    d = _covs(df)
    d = d.loc[:, d.std() > 0]  # covariável sem variação no treino (ex.: Passe Copa antes de 2026) sai do modelo
    d["duracao"] = df["duracao_meses"].to_numpy()
    d["evento"] = df["evento"].to_numpy()
    d["plano"] = df["plano"].to_numpy()
    return CoxPHFitter().fit(d, "duracao", "evento", strata=["plano"])


def prob_cancelar(cph: CoxPHFitter, df: pd.DataFrame, h: float = H_SCORE) -> np.ndarray:
    """P(cancelar em até h meses) por assinante, a partir do modelo ajustado (baseline por plano)."""
    d = _covs(df)[[c for c in cph.params_.index]]
    d["plano"] = df["plano"].to_numpy()
    surv = cph.predict_survival_function(d, times=[h])
    # com estratos o lifelines devolve as colunas agrupadas por estrato: realinha pelo índice original
    return 1.0 - surv.iloc[0].reindex(d.index).to_numpy(float)


def _truncado(df: pd.DataFrame, h: float) -> tuple[np.ndarray, np.ndarray]:
    dur = df["duracao_meses"].to_numpy()
    ev = df["evento"].to_numpy()
    e = (ev == 1) & (dur <= h)
    return np.minimum(dur, h), e.astype(int)


def cindex_h(df: pd.DataFrame, risco: np.ndarray, h: float = H_SCORE) -> float:
    dur, ev = _truncado(df, h)
    return float(concordance_index(dur, -risco, ev))


def calibracao(df: pd.DataFrame, risco: np.ndarray, h: float = H_SCORE, n_faixas: int = N_FAIXAS) -> list[dict]:
    """Previsto (média do risco) × observado (Kaplan-Meier em h) por quintil de risco."""
    q = pd.qcut(pd.Series(risco).rank(method="first"), n_faixas, labels=False).to_numpy()
    linhas = []
    for k in range(n_faixas):
        s = df.iloc[np.where(q == k)[0]]
        pt = K.km_ponto(s["duracao_meses"], s["evento"], h)
        obs = None if not pt["estimavel"] else 1.0 - pt["valor"]
        linhas.append({"faixa": k + 1, "n": int(len(s)), "previsto": float(risco[q == k].mean()),
                       "observado": obs, "lo": None if obs is None else 1.0 - pt["hi"],
                       "hi": None if obs is None else 1.0 - pt["lo"], "n_risco": int(pt["n_risco"])})
    return linhas


def captura(df: pd.DataFrame, risco: np.ndarray, h: float = H_SCORE, topo: float = 0.2) -> dict:
    """Entre quem tem h meses de seguimento possível, que fração dos cancelamentos em h meses cai no topo do score?"""
    el = (df["seguimento_max_meses"].to_numpy() >= h)
    d = df[el]
    r = risco[el]
    cancel = ((d["evento"] == 1) & (d["duracao_meses"] <= h)).to_numpy()
    corte = np.quantile(r, 1 - topo)
    top = r >= corte
    return {"topo": topo, "n_elegiveis": int(len(d)), "taxa_base": float(cancel.mean()),
            "taxa_topo": float(cancel[top].mean()), "taxa_resto": float(cancel[~top].mean()),
            "lift": float(cancel[top].mean() / cancel.mean()),
            "captura": float(cancel[top].sum() / max(cancel.sum(), 1))}


def agregado_fora_do_tempo(df_teste: pd.DataFrame, previsto_s: dict[int, np.ndarray]) -> list[dict]:
    """Retenção agregada prevista × observada (Kaplan-Meier) no período de teste, em M3 e M6."""
    out = []
    for h, s_prev in previsto_s.items():
        pt = K.km_ponto(df_teste["duracao_meses"], df_teste["evento"], h)
        if not pt["estimavel"]:
            continue
        prev = float(s_prev.mean())
        out.append({"h": h, "previsto": prev, "observado": pt["valor"], "lo": pt["lo"], "hi": pt["hi"],
                    "cobre": bool(pt["lo"] <= prev <= pt["hi"]), "erro_pp": prev - pt["valor"]})
    return out


def analise_fora_do_tempo(df: pd.DataFrame, lat) -> dict:
    treino = truncar_em(df, T0)
    teste_mask = (df["data_inicio"] > pd.Timestamp(T0)).to_numpy()
    teste = df[teste_mask]
    cph = ajustar_score(treino)
    r_tr = prob_cancelar(cph, treino)
    r_te = prob_cancelar(cph, teste)
    # risco individual VERDADEIRO (só existe porque os dados são sintéticos): teto de qualquer modelo
    r_ver_te = 1.0 - lat.s_true_mes[teste_mask, H_SCORE]
    s3 = 1.0 - prob_cancelar(cph, teste, 3)
    s6 = 1.0 - r_te
    return {
        "t0": str(T0), "horizonte": H_SCORE,
        "n_treino": int(len(treino)), "n_eventos_treino": int(treino["evento"].sum()),
        "n_teste": int(len(teste)), "n_eventos_teste": int(teste["evento"].sum()),
        "seguimento_max_teste": float(teste["seguimento_max_meses"].max()),
        "cindex": {"treino": cindex_h(treino, r_tr), "teste": cindex_h(teste, r_te),
                   "teto_verdadeiro": cindex_h(teste, r_ver_te)},
        "calibracao": calibracao(teste, r_te),
        "captura": captura(teste, r_te),
        "agregado": agregado_fora_do_tempo(teste, {3: s3, 6: s6}),
        "coefs": [{"nome": k, "hr": float(np.exp(v))} for k, v in cph.params_.items()],
    }


# ------------------------------------------------------------------------------------
# Score de risco por assinante (ajustado em TODA a base) e alvo da ação do mês 3
# ------------------------------------------------------------------------------------

def pontuar(df: pd.DataFrame, cph: CoxPHFitter | None = None) -> pd.DataFrame:
    """Score por assinante: probabilidade de cancelar em até 6 meses e decil de risco (1 = menor, 10 = maior)."""
    cph = cph or ajustar_score(df)
    r = prob_cancelar(cph, df)
    dec = pd.qcut(pd.Series(r).rank(method="first"), 10, labels=False).to_numpy() + 1
    return pd.DataFrame({"id_assinante": df["id_assinante"].to_numpy(), "prob_cancelar_6m": r, "decil_risco": dec})


def alvo_acao(df: pd.DataFrame, acao: dict, tab_hr: list[dict]) -> dict:
    """Quem tratar no mês 3: terços de risco entre os assinantes da Black Friday que chegaram ao mês 3.

    O score vem do modelo treinado em T0 (a Black Friday mais recente é pós-T0, então o score é fora do tempo para
    ela). Por terço: cancelamento observado no mês 3–4 (Kaplan-Meier), o excesso atribuível ao penhasco
    (mesma conta da ação geral, com o HR do Cox corrigido), o benefício esperado por assinante tratado e a
    efetividade de equilíbrio. Tudo que é valor em R$ é PROJEÇÃO.
    """
    hr = {r["nome"]: r for r in tab_hr}["promo_penhasco"]["hr"]
    cph = ajustar_score(truncar_em(df, T0))
    bf = df[(df["oferta_entrada"] == "black_friday") & (df["duracao_meses"] > 3.0)].copy()
    bf["risco"] = prob_cancelar(cph, bf)
    bf["faixa"] = pd.qcut(bf["risco"].rank(method="first"), 3, labels=False)
    v_ret = acao["projetado"]["valor_assinante_retido"]
    custo = acao["projetado"]["custo_por_assinante"]
    e_base = acao["projetado"]["efetividade_base"]
    nomes = {0: "menor risco", 1: "risco médio", 2: "maior risco"}
    linhas = []
    for k in range(3):
        s = bf[bf["faixa"] == k]
        pc = K.prob_condicional(s["duracao_meses"], s["evento"], 3.0, 4.0)
        q = float(pc["prob"])
        q_cf = 1.0 - (1.0 - q) ** (1.0 / hr)
        exc = q - q_cf
        ben = e_base * exc * v_ret
        linhas.append({"faixa": nomes[k], "n": int(len(s)), "risco_medio_modelo": float(s["risco"].mean()),
                       "q_observado": q, "excesso": float(exc), "valor_retido_esperado": float(exc * v_ret),
                       "beneficio_por_tratado": float(ben), "liquido_por_tratado": float(ben - custo),
                       "efetividade_equilibrio": float(custo / (exc * v_ret)) if exc > 0 else None,
                       "vale_tratar": bool(ben > custo)})
    n_tot = sum(x["n"] for x in linhas)
    liq_todos = sum(x["n"] * x["liquido_por_tratado"] for x in linhas)
    top = linhas[-1]
    return {
        "n_bf_mes3": int(n_tot), "faixas": linhas, "liquido_tratar_todos": float(liq_todos),
        "liquido_tratar_maior_risco": float(top["n"] * top["liquido_por_tratado"]),
        "pct_tratado_maior_risco": float(top["n"] / n_tot),
        "razao_excesso_alto_baixo": float(linhas[-1]["excesso"] / linhas[0]["excesso"]) if linhas[0]["excesso"] > 0 else None,
        "efetividade_base": e_base, "custo_por_assinante": custo,
    }


def desenho_teste(acao: dict, alvo: dict) -> dict:
    """Desenho do teste A/B da ação do mês 3: n por braço para detectar cada efetividade, e o que cabe numa campanha."""
    p0 = acao["medido"]["q_penhasco"]
    exc = acao["medido"]["periodos"]["promo_penhasco"]["excesso"]
    vivos = acao["projetado"]["vivos_mes3"]
    pw = NormalIndPower()
    linhas = []
    for e in C.ACAO_EFETIVIDADES:
        p1 = p0 - e * exc
        h = abs(float(proportion_effectsize(p0, p1)))
        n_braco = float(pw.solve_power(effect_size=h, alpha=C.ALPHA, power=0.8, ratio=1.0, alternative="two-sided"))
        linhas.append({"efetividade": e, "p_controle": float(p0), "p_tratamento": float(p1),
                       "n_por_braco": float(np.ceil(n_braco)), "n_total": float(2 * np.ceil(n_braco)),
                       "campanhas_necessarias": float(2 * np.ceil(n_braco) / vivos)})
    h_min = float(pw.solve_power(nobs1=vivos / 2.0, alpha=C.ALPHA, power=0.8, ratio=1.0, alternative="two-sided"))
    # menor p1 detectável com a coorte de referência: inverte o tamanho de efeito de Cohen h
    phi0 = 2.0 * np.arcsin(np.sqrt(p0))
    p1_min = float(np.sin((phi0 - h_min) / 2.0) ** 2)
    return {
        "desfecho_primario": "cancelamento entre o mês 3 e o mês 4 entre quem chegou ao mês 3",
        "randomizacao": "hash determinístico do id do assinante, 50/50, feita no início do mês 3",
        "alpha": C.ALPHA, "poder": 0.8, "vivos_mes3_coorte": float(vivos), "linhas": linhas,
        "efetividade_minima_detectavel": float((p0 - p1_min) / exc),
        "p1_minimo_detectavel": p1_min,
    }


def analise(df: pd.DataFrame, lat, acao: dict, tab_hr: list[dict]) -> dict:
    fora = analise_fora_do_tempo(df, lat)
    alvo = alvo_acao(df, acao, tab_hr)
    return {"fora_do_tempo": fora, "alvo_acao": alvo, "teste_acao": desenho_teste(acao, alvo)}
