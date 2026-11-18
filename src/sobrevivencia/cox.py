"""Regressão de Cox: modelo ingênuo (riscos proporcionais), diagnóstico de Schoenfeld e correção.

* Modelo ingênuo: uma linha por assinante, covariáveis fixas, premissa de riscos proporcionais.
* Diagnóstico: teste de Schoenfeld (escore de Grambsch-Therneau) implementado aqui com suporte a
  estratos e a entrada tardia (dados em episódios), conferido contra o lifelines nos testes.
* Correção: estratificação por plano + efeito da promoção POR PERÍODOS de idade + reajuste de preço
  como covariável dependente do calendário (ambos exigem dividir o tempo em episódios).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from lifelines import CoxPHFitter
from scipy import stats

from . import config as C

# Faixas de idade (meses de vida) do teste de Schoenfeld "por faixas": [0,3) base; depois 4 faixas
FAIXAS_PH = (3.0, 4.0, 6.0, 12.0)

ROTULOS = {
    "canal_busca_paga": "Canal: busca paga (vs orgânico)",
    "canal_midia_paga": "Canal: mídia paga Meta (vs orgânico)",
    "canal_social": "Canal: social (vs orgânico)",
    "canal_indicacao": "Canal: indicação (vs orgânico)",
    "canal_email_crm": "Canal: e-mail/CRM (vs orgânico)",
    "plano_anual": "Plano: anual (vs mensal)",
    "plano_combo": "Plano: combo (vs mensal)",
    "plano_estudante": "Plano: estudante (vs mensal)",
    "disp_desktop": "Dispositivo: desktop (vs mobile)",
    "disp_tablet": "Dispositivo: tablet (vs mobile)",
    "eng_z": "Engajamento (+1 desvio-padrão)",
    "oferta_bf": "Entrou na Black Friday (efeito único)",
    "oferta_copa": "Entrou pelo Passe Copa",
    "promo_vigente": "Promoção vigente (meses 0–3)",
    "promo_penhasco": "Penhasco (mês 3–4, 1º mês a preço cheio)",
    "promo_pos": "Pós-penhasco (meses 4–6)",
    "reajuste_exposto": "Reajuste de preço (Mensal/Combo, jul–ago/26)",
}


def verdade_hr() -> dict[str, float | None]:
    """HR plantado por coeficiente (None = não aplicável como razão única)."""
    v: dict[str, float | None] = {f"canal_{c}": C.HR_CANAL[c] for c in C.CANAIS if c != C.CANAL_REF}
    v.update({"plano_combo": C.HR_PLANO["combo"], "plano_estudante": C.HR_PLANO["estudante"],
              "plano_anual": None,  # efeito não proporcional (pico na renovação)
              "disp_desktop": C.HR_DISPOSITIVO["desktop"], "disp_tablet": C.HR_DISPOSITIVO["tablet"],
              "eng_z": C.HR_ENGAJ_POR_DP, "oferta_copa": C.HR_PASSE_COPA,
              "oferta_bf": None,  # efeito por período (0,85 / 3,0 / 1,35)
              "reajuste_exposto": C.HR_REAJUSTE})
    for nome, p in C.HR_PROMO_PERIODOS.items():
        v[nome] = p["hr"]
    return v


# ------------------------------------------------------------------------------------
# Matrizes de covariáveis
# ------------------------------------------------------------------------------------

def covariaveis_base(df: pd.DataFrame, *, plano_dummies: bool = True) -> pd.DataFrame:
    X = pd.DataFrame(index=df.index)
    for c in C.CANAIS:
        if c != C.CANAL_REF:
            X[f"canal_{c}"] = (df["canal"] == c).astype(float)
    if plano_dummies:
        for p in ("anual", "combo", "estudante"):
            X[f"plano_{p}"] = (df["plano"] == p).astype(float)
    for d in ("desktop", "tablet"):
        X[f"disp_{d}"] = (df["dispositivo"] == d).astype(float)
    X["eng_z"] = (df["engajamento_pre"] - C.ENG_MEDIA) / C.ENG_DP
    X["oferta_copa"] = (df["oferta_entrada"] == "passe_copa").astype(float)
    return X


def dados_ingenuo(df: pd.DataFrame) -> pd.DataFrame:
    X = covariaveis_base(df)
    X["oferta_bf"] = (df["oferta_entrada"] == "black_friday").astype(float)
    X["duracao"] = df["duracao_meses"].to_numpy()
    X["evento"] = df["evento"].to_numpy()
    return X


def episodios(df: pd.DataFrame) -> pd.DataFrame:
    """Divide o tempo de cada assinante em episódios (start, stop] com covariáveis variáveis.

    Cortes: idades 3, 4 e 6 meses para quem entrou pela Black Friday (promoção por períodos) e as
    idades que correspondem ao início/fim do reajuste de preço para Mensal/Combo (calendário).
    """
    dias = C.DIAS_POR_MES
    ini = df["data_inicio"]
    a_ini = ((pd.Timestamp(C.REAJUSTE_INI) - ini).dt.days / dias).to_numpy()
    a_fim = (((pd.Timestamp(C.REAJUSTE_FIM) - ini).dt.days + 1) / dias).to_numpy()
    bf = (df["oferta_entrada"] == "black_friday").to_numpy()
    rex = df["plano"].isin(C.REAJUSTE_PLANOS).to_numpy()
    dur = df["duracao_meses"].to_numpy()
    ev = df["evento"].to_numpy()
    cb = [p["k_ini"] for p in C.HR_PROMO_PERIODOS.values()][1:] + [list(C.HR_PROMO_PERIODOS.values())[-1]["k_fim"]]

    linhas = []
    for i in range(len(df)):
        cortes = {0.0}
        if bf[i]:
            cortes.update(float(x) for x in cb)
        if rex[i]:
            cortes.update((float(a_ini[i]), float(a_fim[i])))
        pts = sorted(c for c in cortes if 0.0 <= c < dur[i])
        pts.append(float(dur[i]))
        for a, b in zip(pts[:-1], pts[1:]):
            if b <= a:
                continue
            p_v = bf[i] and a < 3.0
            p_p = bf[i] and 3.0 <= a < 4.0
            p_q = bf[i] and 4.0 <= a < 6.0
            r = rex[i] and a >= a_ini[i] - 1e-9 and a < a_fim[i] - 1e-9
            linhas.append((i, a, b, int(ev[i] == 1 and b == dur[i]), int(p_v), int(p_p), int(p_q), int(r)))
    ep = pd.DataFrame(linhas, columns=["i", "start", "stop", "evento", "promo_vigente", "promo_penhasco",
                                       "promo_pos", "reajuste_exposto"])
    base = covariaveis_base(df, plano_dummies=False).iloc[ep["i"].to_numpy()].reset_index(drop=True)
    ep = pd.concat([ep, base], axis=1)
    ep["plano"] = df["plano"].to_numpy()[ep["i"].to_numpy()]
    ep["id_assinante"] = df["id_assinante"].to_numpy()[ep["i"].to_numpy()]
    return ep


# ------------------------------------------------------------------------------------
# Ajustes
# ------------------------------------------------------------------------------------

def ajustar_ingenuo(df: pd.DataFrame) -> tuple[CoxPHFitter, pd.DataFrame]:
    d = dados_ingenuo(df)
    cph = CoxPHFitter().fit(d, "duracao", "evento")
    return cph, d


COVS_CORRIGIDO = ["canal_busca_paga", "canal_midia_paga", "canal_social", "canal_indicacao",
                  "canal_email_crm", "disp_desktop", "disp_tablet", "eng_z", "oferta_copa",
                  "promo_vigente", "promo_penhasco", "promo_pos", "reajuste_exposto"]


def ajustar_corrigido(ep: pd.DataFrame) -> tuple[CoxPHFitter, pd.DataFrame]:
    """Estratificado por plano; promoção por períodos; reajuste de calendário."""
    d = ep[COVS_CORRIGIDO + ["start", "stop", "evento", "plano"]].copy()
    cph = CoxPHFitter().fit(d, "stop", "evento", entry_col="start", strata=["plano"])
    return cph, d


def ajustar_complementar(df: pd.DataFrame, ep: pd.DataFrame) -> tuple[CoxPHFitter, pd.DataFrame]:
    """Sem plano anual e sem estratos: recupera o HR de plano (combo/estudante) onde PH vale."""
    m = ep["plano"] != "anual"
    d = ep.loc[m, COVS_CORRIGIDO + ["start", "stop", "evento", "plano"]].copy()
    d["plano_combo"] = (d["plano"] == "combo").astype(float)
    d["plano_estudante"] = (d["plano"] == "estudante").astype(float)
    d = d.drop(columns="plano")
    cph = CoxPHFitter().fit(d, "stop", "evento", entry_col="start")
    return cph, d


def tabela_hr(cph: CoxPHFitter, verdade: dict | None = None) -> list[dict]:
    verdade = verdade_hr() if verdade is None else verdade
    s = cph.summary
    linhas = []
    for nome, r in s.iterrows():
        hr, lo, hi = float(np.exp(r["coef"])), float(np.exp(r["coef lower 95%"])), float(np.exp(r["coef upper 95%"]))
        v = verdade.get(nome)
        linhas.append({
            "nome": nome, "rotulo": ROTULOS.get(nome, nome), "coef": float(r["coef"]),
            "se": float(r["se(coef)"]), "hr": hr, "lo": lo, "hi": hi, "p": float(r["p"]),
            "verdade": v,
            "cobre": None if v is None else bool(lo <= v <= hi),
            "erro_rel": None if v is None else float(hr / v - 1.0),
        })
    return linhas


# ------------------------------------------------------------------------------------
# Teste de riscos proporcionais (Schoenfeld) com estratos e entrada tardia
# ------------------------------------------------------------------------------------

def _momentos(X, beta, start, stop, evento, strata):
    """Resíduos de Schoenfeld r_j (não escalados) e variâncias V_j em cada tempo de evento."""
    n, p = X.shape
    w = np.exp(X @ beta)
    tj, rj, Vj = [], [], []
    for s in np.unique(strata):
        m = strata == s
        Xs, ws, st, sp, ev = X[m], w[m], start[m], stop[m], evento[m]
        for i in np.where(ev == 1)[0]:
            t = sp[i]
            rs = (st < t) & (sp >= t)
            ww = ws[rs]
            Xr = Xs[rs]
            S0 = ww.sum()
            xbar = (ww[:, None] * Xr).sum(axis=0) / S0
            V = (Xr * ww[:, None]).T @ Xr / S0 - np.outer(xbar, xbar)
            tj.append(t)
            rj.append(Xs[i] - xbar)
            Vj.append(V)
    return np.array(tj), np.array(rj), np.array(Vj)


def _matriz_faixas(t: np.ndarray) -> np.ndarray:
    """Indicadores das faixas de idade [3,4), [4,6), [6,12), >=12 (base = [0,3))."""
    bordas = (0.0,) + FAIXAS_PH + (np.inf,)
    return np.column_stack([((t >= bordas[k]) & (t < bordas[k + 1])).astype(float)
                            for k in range(1, len(bordas) - 1)])


def _escore(U, Itt, Itb, Ibb) -> tuple[float, int]:
    """Estatística de escore e graus de liberdade (posto efetivo da variância)."""
    var = Itt - Itb @ np.linalg.solve(Ibb, Itb.T)
    var = (var + var.T) / 2
    w, v = np.linalg.eigh(var)
    ok = w > 1e-8 * max(1.0, float(np.max(np.abs(w))))
    if not ok.any():
        return 0.0, 0
    proj = v[:, ok].T @ U
    return float(np.sum(proj**2 / w[ok])), int(ok.sum())


def teste_ph(dados: pd.DataFrame, covs: list[str], beta: np.ndarray, *, stop: str, evento: str,
             start: str | None = None, strata: str | None = None) -> dict:
    """Teste de Schoenfeld (escore) para cada covariável.

    * ``rank``: efeito varia linearmente com o rank do tempo (1 gl) — o teste "padrão".
    * ``faixas``: efeito varia por faixa de idade (4 gl) — detecta efeitos que sobem e descem.
    """
    X = dados[covs].to_numpy(float)
    n = len(X)
    st = dados[start].to_numpy(float) if start else np.zeros(n)
    sp = dados[stop].to_numpy(float)
    ev = dados[evento].to_numpy(int)
    sr = dados[strata].to_numpy() if strata else np.zeros(n, int)
    t, r, V = _momentos(X, np.asarray(beta, float), st, sp, ev, sr)
    d, p = r.shape
    Ibb = V.sum(axis=0)

    g_rank = (stats.rankdata(t) - (d + 1) / 2.0)[:, None]
    G_fx = _matriz_faixas(t)
    ativas = G_fx.sum(axis=0) > 0
    G_fx = G_fx[:, ativas]

    out = {"covariaveis": {}, "d_eventos": int(d)}
    for k, nome in enumerate(covs):
        res = {}
        for tipo, G in (("rank", g_rank), ("faixas", G_fx)):
            # descarta faixas em que a covariável não varia entre os em risco (sem informação)
            G = G[:, ((G != 0) * V[:, k, k][:, None]).sum(axis=0) > 1e-10]
            if G.shape[1] == 0:
                res[tipo] = {"chi2": 0.0, "df": 0, "p": 1.0}
                continue
            U = G.T @ r[:, k]
            Itt = G.T @ (G * V[:, k, k][:, None])
            Itb = G.T @ V[:, k, :]
            chi2, df_ = _escore(U, Itt, Itb, Ibb)
            res[tipo] = {"chi2": chi2, "df": int(df_),
                         "p": float(stats.chi2.sf(chi2, df_)) if df_ > 0 else 1.0}
        out["covariaveis"][nome] = res
    # teste global (todas as covariáveis, tendência em rank)
    g = g_rank[:, 0]
    U = (g[:, None] * r).sum(axis=0)
    Itt = np.einsum("j,jkl->kl", g**2, V)
    Itb = np.einsum("j,jkl->kl", g, V)
    chi2g, dfg = _escore(U, Itt, Itb, Ibb)
    out["global_rank"] = {"chi2": chi2g, "df": int(dfg), "p": float(stats.chi2.sf(chi2g, dfg))}
    # efeito local por faixa (média do resíduo escalado = log-HR local)
    Isc = np.linalg.inv(Ibb)
    esc = np.asarray(beta, float)[None, :] + d * (r @ Isc.T)
    bordas = (0.0,) + FAIXAS_PH + (np.inf,)
    local = {}
    for k, nome in enumerate(covs):
        linhas = []
        for b in range(len(bordas) - 1):
            m = (t >= bordas[b]) & (t < bordas[b + 1])
            if m.sum() >= 5:
                linhas.append({"ini": bordas[b], "fim": None if np.isinf(bordas[b + 1]) else bordas[b + 1],
                               "n_eventos": int(m.sum()), "hr_local": float(np.exp(esc[m, k].mean()))})
        local[nome] = linhas
    out["efeito_local"] = local
    out["_t"], out["_esc"] = t, esc
    return out


def resumo_ph(res: dict, covs: list[str], alpha: float = C.ALPHA) -> list[dict]:
    linhas = []
    for nome in covs:
        r = res["covariaveis"][nome]
        linhas.append({"nome": nome, "rotulo": ROTULOS.get(nome, nome),
                       "chi2_rank": r["rank"]["chi2"], "p_rank": r["rank"]["p"],
                       "chi2_faixas": r["faixas"]["chi2"], "p_faixas": r["faixas"]["p"],
                       "df_faixas": r["faixas"]["df"],
                       "viola": bool(min(r["rank"]["p"], r["faixas"]["p"]) < alpha / len(covs))})
    return linhas


# ------------------------------------------------------------------------------------
# Concordância (C-index) com covariáveis dependentes do tempo
# ------------------------------------------------------------------------------------

def concordancia_td(dados: pd.DataFrame, covs: list[str], beta: np.ndarray, *, stop: str, evento: str,
                    start: str | None = None, strata: str | None = None) -> float:
    """C-index de Harrell: em cada evento, compara o preditor linear de quem falhou com o de quem
    seguia em risco (usando as covariáveis vigentes naquele instante); empates valem 0,5."""
    X = dados[covs].to_numpy(float)
    lp = X @ np.asarray(beta, float)
    n = len(X)
    st = dados[start].to_numpy(float) if start else np.zeros(n)
    sp = dados[stop].to_numpy(float)
    ev = dados[evento].to_numpy(int)
    sr = dados[strata].to_numpy() if strata else np.zeros(n, int)
    conc = comp = 0.0
    for s in np.unique(sr):
        m = sr == s
        l, a, b, e = lp[m], st[m], sp[m], ev[m]
        for i in np.where(e == 1)[0]:
            t = b[i]
            rs = (a < t) & (b > t)
            if not rs.any():
                continue
            li = l[rs]
            conc += (l[i] > li).sum() + 0.5 * (l[i] == li).sum()
            comp += rs.sum()
    return float(conc / comp)
