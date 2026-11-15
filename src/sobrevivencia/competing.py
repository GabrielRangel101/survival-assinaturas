"""G. Riscos competitivos: incidência acumulada por causa (estimador de Aalen-Johansen).

Causas: voluntário, involuntário (falha de pagamento) e fim de contrato (anual não renovado).
A incidência acumulada (CIF) respeita que quem sai por uma causa deixa de estar sob risco das
outras; "1 - KM tratando as outras causas como censura" SUPERESTIMA a incidência.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C
from . import km as K


def aalen_johansen(duracao, causa, causas=C.CAUSAS) -> dict:
    """CIF por causa. ``causa`` = '' (ou NaN) para censurado."""
    dur = np.asarray(duracao, float)
    cz = np.asarray(["" if (c is None or (isinstance(c, float) and np.isnan(c))) else c for c in causa], dtype=object)
    ordem = np.argsort(dur, kind="stable")
    dur, cz = dur[ordem], cz[ordem]
    ev = cz != ""
    tempos = np.unique(dur[ev])
    n = len(dur) - np.searchsorted(dur, tempos, side="left")
    d_k = {}
    for k in causas:
        idx = np.searchsorted(tempos, dur[ev & (cz == k)])
        d_k[k] = np.bincount(idx, minlength=len(tempos)).astype(float)
    d_tot = sum(d_k.values())
    S_apos = np.cumprod(1 - d_tot / n)
    S_antes = np.concatenate([[1.0], S_apos[:-1]])
    cif = {k: np.cumsum(S_antes * d_k[k] / n) for k in causas}
    return {"t": tempos, "S": S_apos, "cif": cif, "n_risco": n}


def cif_em(aj: dict, t: float) -> dict:
    i = np.searchsorted(aj["t"], t, side="right") - 1
    if i < 0:
        return {k: 0.0 for k in aj["cif"]}
    return {k: float(v[i]) for k, v in aj["cif"].items()}


def um_menos_km_outras_censuradas(duracao, causa, k: str, t: float) -> float:
    """O erro clássico: 1 - KM tratando as OUTRAS causas como censura."""
    dur = np.asarray(duracao, float)
    ev = (np.asarray(causa) == k).astype(int)
    return float(1 - K.km_curve(dur, ev).em(t)[0])


def analise(df: pd.DataFrame, gt: dict, n_boot: int = 300, seed: int = C.SEED + 3000) -> dict:
    dur = df["duracao_meses"].to_numpy()
    causa = df["causa"].to_numpy()
    aj = aalen_johansen(dur, causa)
    grade = np.arange(0, 25)
    curvas = {k: [round(cif_em(aj, float(t))[k], 4) for t in grade] for k in C.CAUSAS}
    todas = [round(float(1 - K.km_curve(dur, df["evento"]).em(float(t))[0]), 4) for t in grade]

    rng = np.random.default_rng(seed)
    horizontes = (6, 12, 18)
    boot = {h: {k: [] for k in C.CAUSAS} for h in horizontes}
    n = len(df)
    for _ in range(n_boot):
        i = rng.integers(0, n, n)
        a = aalen_johansen(dur[i], causa[i])
        for h in horizontes:
            c = cif_em(a, float(h))
            for k in C.CAUSAS:
                boot[h][k].append(c[k])
    pontos = {}
    for h in horizontes:
        c = cif_em(aj, float(h))
        pontos[f"m{h}"] = {
            k: {"est": c[k], "lo": float(np.percentile(boot[h][k], 2.5)),
                "hi": float(np.percentile(boot[h][k], 97.5)),
                "um_menos_km": um_menos_km_outras_censuradas(dur, causa, k, float(h))}
            for k in C.CAUSAS
        }
        pontos[f"m{h}"]["soma_cif"] = float(sum(c.values()))
        pontos[f"m{h}"]["um_menos_km_todas"] = float(1 - K.km_curve(dur, df["evento"]).em(float(h))[0])
    # por plano em M12 (anual: o fim de contrato domina)
    por_plano = {}
    for p in C.PLANOS:
        sub = df[df["plano"] == p]
        a = aalen_johansen(sub["duracao_meses"].to_numpy(), sub["causa"].to_numpy())
        c = cif_em(a, 13.0)  # M13: já inclui a janela da renovação (intervalo 12–13)
        por_plano[p] = {"rotulo": C.PLANOS_ROTULO[p], "n": int(len(sub)),
                        "cif_m13": c, "total_m13": float(sum(c.values()))}
    verdade = gt["cif_verdade_m12"]
    return {"curvas": curvas, "curva_total": todas, "grade": [int(x) for x in grade],
            "pontos": pontos, "por_plano": por_plano, "n_boot": n_boot,
            "verdade_m12": verdade,
            "participacao_m12": {k: pontos["m12"][k]["est"] / pontos["m12"]["soma_cif"] for k in C.CAUSAS}}
