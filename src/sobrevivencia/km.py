"""Kaplan-Meier, log-rank, correção de Holm, RMST e hazard empírico (implementação própria em numpy).

Convenções: duração em meses; ``evento`` = 1 se cancelou, 0 se censurado à direita.
No tempo t, "em risco" = quem tem duração >= t. Estas funções são verificadas nos testes
contra um exemplo calculado à mão e contra o ``lifelines``.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import stats

from . import config as C


@dataclass
class KM:
    """Curva de Kaplan-Meier (passo) com variância de Greenwood."""

    t: np.ndarray        # tempos distintos de evento
    n_risco: np.ndarray  # em risco logo antes de t
    d: np.ndarray        # eventos em t
    S: np.ndarray        # sobrevivência logo após t
    g: np.ndarray        # soma cumulativa d/(n(n-d)) (Greenwood)
    dur_ord: np.ndarray  # durações ordenadas (para contar em risco em qualquer t)

    # ---- avaliação em tempos arbitrários ---------------------------------------
    def em_risco(self, t: float) -> int:
        """Número de assinantes com duração >= t."""
        return int(len(self.dur_ord) - np.searchsorted(self.dur_ord, t, side="left"))

    def em(self, t: float, nivel: float = 0.95) -> tuple[float, float, float]:
        """S(t) e IC (log-log, Greenwood). Antes do 1º evento: (1, 1, 1)."""
        i = np.searchsorted(self.t, t, side="right") - 1
        if i < 0:
            return 1.0, 1.0, 1.0
        s, g = float(self.S[i]), float(self.g[i])
        return (s, *_ic_loglog(s, g, nivel))

    def em_varios(self, ts: np.ndarray) -> np.ndarray:
        ts = np.asarray(ts, dtype=float)
        if len(self.t) == 0:  # sem eventos: S = 1 em todo t
            return np.ones(ts.shape)
        idx = np.searchsorted(self.t, ts, side="right") - 1
        return np.where(idx >= 0, self.S[np.maximum(idx, 0)], 1.0)


def _ic_loglog(s: float, g: float, nivel: float = 0.95) -> tuple[float, float]:
    if s <= 0.0:
        return 0.0, 0.0
    if s >= 1.0 or g <= 0.0:
        return s, s
    z = stats.norm.ppf(0.5 + nivel / 2)
    se_ll = np.sqrt(g) / abs(np.log(s))
    return float(s ** np.exp(z * se_ll)), float(s ** np.exp(-z * se_ll))


def km_curve(duracao, evento) -> KM:
    dur = np.asarray(duracao, dtype=float)
    ev = np.asarray(evento).astype(int)
    ord_ = np.sort(dur)
    t_ev, d = np.unique(dur[ev == 1], return_counts=True)
    n = len(dur) - np.searchsorted(ord_, t_ev, side="left")
    fator = 1.0 - d / n
    S = np.cumprod(fator)
    with np.errstate(divide="ignore", invalid="ignore"):
        inc = np.where(n > d, d / (n * (n - d)), np.inf)
    g = np.cumsum(inc)
    return KM(t=t_ev, n_risco=n, d=d, S=S, g=g, dur_ord=ord_)


def km_ponto(duracao, evento, h: float, nivel: float = 0.95) -> dict:
    """S(h) com IC e n em risco em h; ``estimavel`` segue MIN_EM_RISCO."""
    km = km_curve(duracao, evento)
    s, lo, hi = km.em(h, nivel)
    n_r = km.em_risco(h)
    return {"valor": s, "lo": lo, "hi": hi, "n_risco": n_r, "estimavel": bool(n_r >= C.MIN_EM_RISCO)}


# ------------------------------------------------------------------------------------
# Log-rank
# ------------------------------------------------------------------------------------

def logrank(duracao, evento, grupo) -> dict:
    """Log-rank para k grupos (qui-quadrado com k-1 gl)."""
    dur = np.asarray(duracao, dtype=float)
    ev = np.asarray(evento).astype(int)
    grupo = np.asarray(grupo)
    nomes = list(dict.fromkeys(sorted(set(grupo.tolist()))))
    t_ev = np.unique(dur[ev == 1])
    T, G = len(t_ev), len(nomes)
    n_g = np.zeros((T, G))
    d_g = np.zeros((T, G))
    for j, nm in enumerate(nomes):
        m = grupo == nm
        ordj = np.sort(dur[m])
        n_g[:, j] = m.sum() - np.searchsorted(ordj, t_ev, side="left")
        te, dc = np.unique(dur[m & (ev == 1)], return_counts=True)
        d_g[np.searchsorted(t_ev, te), j] = dc
    n = n_g.sum(axis=1)
    d = d_g.sum(axis=1)
    obs = d_g.sum(axis=0)
    esp = (d[:, None] * n_g / n[:, None]).sum(axis=0)
    # covariância hipergeométrica
    c = np.where(n > 1, d * (n - d) / np.maximum(n - 1, 1), 0.0)  # d(n-d)/(n-1)
    A = (n_g * (c / n)[:, None]).sum(axis=0)       # termo diagonal: sum c * n_g / n
    B = (n_g.T * (c / n**2)) @ n_g                 # sum c * n_g * n_h / n^2
    V = np.diag(A) - B
    u = (obs - esp)[:-1]
    chi2 = float(u @ np.linalg.solve(V[:-1, :-1], u))
    df = G - 1
    return {"chi2": chi2, "df": df, "p": float(stats.chi2.sf(chi2, df)),
            "observados": dict(zip(nomes, obs.tolist())), "esperados": dict(zip(nomes, esp.tolist()))}


def logrank_pares_holm(duracao, evento, grupo) -> list[dict]:
    """Log-rank de todos os pares, com correção de Holm sobre a família de pares."""
    from itertools import combinations
    from statsmodels.stats.multitest import multipletests

    dur = np.asarray(duracao, dtype=float)
    ev = np.asarray(evento).astype(int)
    grupo = np.asarray(grupo)
    nomes = sorted(set(grupo.tolist()))
    linhas = []
    for a, b in combinations(nomes, 2):
        m = (grupo == a) | (grupo == b)
        r = logrank(dur[m], ev[m], grupo[m])
        linhas.append({"a": a, "b": b, "chi2": r["chi2"], "p": r["p"]})
    ps = np.array([x["p"] for x in linhas])
    rej, p_holm, _, _ = multipletests(ps, alpha=C.ALPHA, method="holm")
    for x, ph, rj in zip(linhas, p_holm, rej):
        x["p_holm"] = float(ph)
        x["significativo_holm"] = bool(rj)
        x["significativo_bruto"] = bool(x["p"] < C.ALPHA)
    return linhas


# ------------------------------------------------------------------------------------
# RMST e hazard empírico
# ------------------------------------------------------------------------------------

def rmst(km: KM, tau: float) -> float:
    """Tempo médio restrito: integral de S(t) de 0 a tau (KM é função de passo)."""
    t = km.t[km.t < tau]
    pontos = np.concatenate([[0.0], t, [tau]])
    s_ant = np.concatenate([[1.0], km.S[: len(t)]])
    return float(np.sum(s_ant * np.diff(pontos)))


def hazard_por_idade(duracao, evento, max_idade: int = 24, passo: float = 1.0) -> list[dict]:
    """Risco empírico por mês de vida: eventos / tempo-sob-risco em [k, k+passo)."""
    dur = np.asarray(duracao, dtype=float)
    ev = np.asarray(evento).astype(int)
    out = []
    for k in np.arange(0, max_idade, passo):
        expo = np.clip(dur, k, k + passo) - k
        eventos = int(((ev == 1) & (dur >= k) & (dur < k + passo)).sum())
        tempo = float(expo.sum())
        out.append({"k": float(k), "eventos": eventos, "tempo_risco": tempo,
                    "n_risco": int((dur >= k).sum()),
                    "taxa": float(eventos / tempo) if tempo > 0 else None})
    return out


def prob_condicional(duracao, evento, k_ini: float, k_fim: float) -> dict:
    """P(cancelar em [k_ini, k_fim) | vivo em k_ini), pela razão de KM."""
    km = km_curve(duracao, evento)
    s0, s1 = km.em(k_ini)[0], km.em(k_fim)[0]
    n0 = km.em_risco(k_ini)
    return {"prob": float(1 - s1 / s0) if s0 > 0 else None, "n_risco": n0}
