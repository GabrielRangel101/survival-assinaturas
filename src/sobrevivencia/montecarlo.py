"""Validação em várias réplicas: o Cox corrigido recupera os efeitos plantados além da seed oficial?

Para cada réplica geramos um novo conjunto sintético (seed diferente, mesmas regras), ajustamos o Cox
corrigido e medimos viés relativo e cobertura do IC 95% de cada efeito com razão única plantada.
"""

from __future__ import annotations

import numpy as np

from . import config as C
from . import cox as X
from . import simulate as S

MC_REPLICAS = 20
MC_REPLICAS_RAPIDO = 5
MC_SEED0 = C.SEED + 5000


def recuperacao(n_rep: int = MC_REPLICAS, n: int = C.N_ASSINANTES, seed0: int = MC_SEED0,
                log=print) -> dict:
    acc: dict[str, list[tuple[float, float, float, bool]]] = {}
    for r in range(n_rep):
        df, _ = S.simular(seed=seed0 + r, n=n)
        ep = X.episodios(df)
        cph, _ = X.ajustar_corrigido(ep)
        for row in X.tabela_hr(cph):
            if row["verdade"] is None:
                continue
            acc.setdefault(row["nome"], []).append((row["hr"], row["lo"], row["hi"], bool(row["cobre"])))
        log(f"    réplica {r + 1}/{n_rep}")
    verdade = X.verdade_hr()
    linhas = []
    for nome, v in acc.items():
        est = np.array([x[0] for x in v])
        linhas.append({
            "nome": nome, "rotulo": X.ROTULOS[nome], "verdade": verdade[nome],
            "media_hr": float(est.mean()), "vies_rel": float(est.mean() / verdade[nome] - 1.0),
            "dp_hr": float(est.std(ddof=1)) if len(est) > 1 else 0.0,
            "cobertura": float(np.mean([x[3] for x in v])),
        })
    cob_total = float(np.mean([x[3] for v in acc.values() for x in v]))
    return {"n_replicas": n_rep, "n": n, "efeitos": linhas, "cobertura_total": cob_total,
            "vies_abs_max": float(max(abs(l["vies_rel"]) for l in linhas)),
            "n_intervalos": int(sum(len(v) for v in acc.values()))}
