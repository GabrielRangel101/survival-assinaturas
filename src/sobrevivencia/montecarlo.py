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
MC_N = 9000   # assinantes por réplica (menor que o oficial, para a validação caber em minutos)


def recuperacao(n_rep: int = MC_REPLICAS, n: int = MC_N, seed0: int = MC_SEED0,
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


# ------------------------------------------------------------------------------------
# Robustez: e se o gerador NÃO espelhasse o modelo?
# ------------------------------------------------------------------------------------

ROB_REPLICAS = 6
ROB_N = 9000
ROB_FRAGILIDADE = 0.5
ROB_DESLOC_DIAS = 15.0
ROB_EFEITOS = ("canal_midia_paga", "canal_indicacao", "eng_z", "oferta_copa", "promo_vigente",
               "promo_penhasco", "promo_pos", "reajuste_exposto")


def _roda_variante(n_rep: int, n: int, seed0: int, **kw) -> dict:
    acc: dict[str, list[tuple[float, bool]]] = {}
    for r in range(n_rep):
        df, _ = S.simular(seed=seed0 + r, n=n, **kw)
        cph, _ = X.ajustar_corrigido(X.episodios(df))
        for row in X.tabela_hr(cph):
            if row["verdade"] is not None:
                acc.setdefault(row["nome"], []).append((row["hr"], bool(row["cobre"])))
    verdade = X.verdade_hr()
    efeitos = []
    for nome in ROB_EFEITOS:
        est = np.array([x[0] for x in acc[nome]])
        efeitos.append({"nome": nome, "rotulo": X.ROTULOS[nome], "verdade": verdade[nome],
                        "media_hr": float(est.mean()), "vies_rel": float(est.mean() / verdade[nome] - 1.0),
                        "cobertura": float(np.mean([x[1] for x in acc[nome]]))})
    todos = [x[1] for v in acc.values() for x in v]
    return {"efeitos": efeitos, "cobertura_total": float(np.mean(todos)),
            "vies_abs_max": float(max(abs(e["vies_rel"]) for e in efeitos))}


def robustez(n_rep: int = ROB_REPLICAS, n: int = ROB_N, seed0: int = MC_SEED0 + 500, log=print) -> dict:
    """Roda o MESMO Cox corrigido em dados cujo gerador difere do modelo e compara com o desenho oficial."""
    out = {"n_replicas": n_rep, "n": n, "variantes": []}
    for vid, descricao, kw in (
        ("oficial", "Mesmo gerador do modelo (referência)", {}),
        ("fragilidade", f"Heterogeneidade não observada (fragilidade gama, variância {ROB_FRAGILIDADE})",
         {"fragilidade": ROB_FRAGILIDADE}),
        ("penhasco_deslocado", f"Penhasco {ROB_DESLOC_DIAS:.0f} dias depois do mês 3–4 que o modelo supõe",
         {"desloc_penhasco_dias": ROB_DESLOC_DIAS}),
    ):
        log(f"    robustez: {vid}")
        v = _roda_variante(n_rep, n, seed0, **kw)
        v.update({"id": vid, "descricao": descricao})
        out["variantes"].append(v)
    return out
