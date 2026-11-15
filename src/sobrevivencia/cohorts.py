"""Desenho (A), retenção ingênua x Kaplan-Meier por safra (B) e comparações por grupo (C)."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from . import config as C
from . import km as K
from .simulate import SAFRAS, rotulo_safra

HORIZONTES_COMPARACAO = (3, 6)  # horizontes extras (comparabilidade entre safras)


# ------------------------------------------------------------------------------------
# A. Desenho
# ------------------------------------------------------------------------------------

def resumo_dados(df: pd.DataFrame) -> dict:
    n = len(df)
    ev = df["evento"] == 1
    causas = df.loc[ev, "causa"].value_counts()
    seg = df["seguimento_max_meses"]
    return {
        "n": int(n),
        "n_eventos": int(ev.sum()),
        "n_censurados": int((~ev).sum()),
        "pct_eventos": float(ev.mean()),
        "pct_censurados": float((~ev).mean()),
        "entrada_ini": str(df["data_inicio"].min().date()),
        "entrada_fim": str(df["data_inicio"].max().date()),
        "corte": str(C.CORTE),
        "seguimento_max_meses": float(seg.max()),
        "seguimento_mediano_meses": float(seg.median()),
        "seguimento_min_meses": float(seg.min()),
        "n_com_12m_possiveis": int((seg >= 12).sum()),
        "n_com_18m_possiveis": int((seg >= 18).sum()),
        "n_com_24m_possiveis": int((seg >= 24).sum()),
        "causas": {c: int(causas.get(c, 0)) for c in C.CAUSAS},
        "por_canal": {c: int((df["canal"] == c).sum()) for c in C.CANAIS},
        "por_plano": {p: int((df["plano"] == p).sum()) for p in C.PLANOS},
        "por_oferta": {o: int((df["oferta_entrada"] == o).sum()) for o in C.OFERTAS},
        "por_dispositivo": {d: int((df["dispositivo"] == d).sum()) for d in C.DISPOSITIVOS},
        "engajamento_medio": float(df["engajamento_pre"].mean()),
    }


# ------------------------------------------------------------------------------------
# Regra de observabilidade
# ------------------------------------------------------------------------------------

def ponto(sub: pd.DataFrame, h: int, *, safra_exige_completa: bool) -> dict:
    """S(h) por KM com IC log-log; só 'ok' se houver tempo de observação.

    Regra: n em risco em h >= MIN_EM_RISCO e, se o grupo é uma safra, TODOS os seus membros
    precisam ter seguimento possível >= h (a safra "tem tempo de observação").
    """
    if len(sub) == 0:
        return {"valor": None, "lo": None, "hi": None, "n_risco": 0, "ok": False,
                "motivo": "sem assinantes"}
    p = K.km_ponto(sub["duracao_meses"], sub["evento"], h)
    seg_min = float(sub["seguimento_max_meses"].min())
    ok = p["estimavel"] and ((not safra_exige_completa) or seg_min >= h)
    motivo = ""
    if not ok:
        if safra_exige_completa and seg_min < h:
            motivo = "safra sem tempo de observação (o último entrante só tem %.1f meses)" % seg_min
        else:
            motivo = "poucos assinantes em risco no horizonte"
    return {"valor": p["valor"] if ok else None, "lo": p["lo"] if ok else None,
            "hi": p["hi"] if ok else None, "n_risco": int(p["n_risco"]), "ok": bool(ok), "motivo": motivo}


def status_meta(p: dict, meta: float | None) -> str | None:
    if meta is None or not p["ok"]:
        return None
    if p["hi"] < meta:
        return "abaixo"
    if p["lo"] > meta:
        return "acima"
    return "indistinguivel"


# ------------------------------------------------------------------------------------
# B. Ingênuo x Kaplan-Meier por safra
# ------------------------------------------------------------------------------------

def tabela_safras(df: pd.DataFrame) -> dict:
    linhas = []
    for i, s in enumerate(SAFRAS, start=1):
        sub = df[df["safra"] == s]
        n = len(sub)
        ativos = int((sub["evento"] == 0).sum())
        hs = {}
        for h in HORIZONTES_COMPARACAO + C.HORIZONTES:
            p = ponto(sub, h, safra_exige_completa=True)
            meta = C.METAS.get(h)
            p["meta"] = meta
            p["status"] = status_meta(p, meta)
            hs[f"m{h}"] = p
        linhas.append({
            "safra": s, "rotulo": rotulo_safra(i), "n": int(n), "ativos": ativos,
            "ret_ingenua": ativos / n, "eventos": int(sub["evento"].sum()),
            "seguimento_min": float(sub["seguimento_max_meses"].min()),
            "seguimento_max": float(sub["seguimento_max_meses"].max()),
            "horizontes": hs,
        })
    # a "retenção ingênua" é função da idade da safra, não da qualidade dela
    idade = np.array([l["seguimento_max"] for l in linhas])
    ingenua = np.array([l["ret_ingenua"] for l in linhas])
    km3 = [l["horizontes"]["m3"]["valor"] for l in linhas]
    ok3 = [v is not None for v in km3]
    rho_ing = float(stats.spearmanr(idade, ingenua).statistic)
    rho_km3 = float(stats.spearmanr(idade[ok3], np.array([v for v in km3 if v is not None])).statistic)
    glob = {}
    for h in HORIZONTES_COMPARACAO + C.HORIZONTES:
        p = ponto(df, h, safra_exige_completa=False)
        p["meta"] = C.METAS.get(h)
        p["status"] = status_meta(p, p["meta"])
        glob[f"m{h}"] = p
    return {
        "safras": linhas,
        "global": glob,
        "ret_ingenua_global": float((df["evento"] == 0).mean()),
        "rho_ingenua_idade": rho_ing,
        "rho_km_m3_idade": rho_km3,
        "melhor_safra_ingenua": max(linhas, key=lambda l: l["ret_ingenua"])["safra"],
        "pior_safra_ingenua": min(linhas, key=lambda l: l["ret_ingenua"])["safra"],
        "n_celulas_m12_preenchidas": int(sum(l["horizontes"]["m12"]["ok"] for l in linhas)),
        "n_celulas_m18_preenchidas": int(sum(l["horizontes"]["m18"]["ok"] for l in linhas)),
        "n_celulas_m24_preenchidas": int(sum(l["horizontes"]["m24"]["ok"] for l in linhas)),
    }


# ------------------------------------------------------------------------------------
# C. Comparações
# ------------------------------------------------------------------------------------

def _linhas_grupo(df: pd.DataFrame, coluna: str, ordem, rotulos: dict | None, *, safra: bool) -> list[dict]:
    out = []
    for g in ordem:
        sub = df[df[coluna] == g]
        km = K.km_curve(sub["duracao_meses"], sub["evento"])
        hs = {}
        for h in C.HORIZONTES:
            p = ponto(sub, h, safra_exige_completa=safra)
            p["meta"] = C.METAS.get(h)
            p["status"] = status_meta(p, p["meta"])
            hs[f"m{h}"] = p
        out.append({"chave": g, "rotulo": (rotulos or {}).get(g, g), "n": int(len(sub)),
                    "eventos": int(sub["evento"].sum()),
                    "mediana": float(km.t[km.S <= 0.5][0]) if (km.S <= 0.5).any() else None,
                    "horizontes": hs})
    return out


def comparacoes(df: pd.DataFrame) -> dict:
    d, e = df["duracao_meses"], df["evento"]
    out: dict = {}
    for nome, col, ordem, rot, safra in (
        ("canal", "canal", C.CANAIS, C.CANAIS_ROTULO, False),
        ("plano", "plano", C.PLANOS, C.PLANOS_ROTULO, False),
        ("safra", "safra", SAFRAS, {s: f"{s} ({rotulo_safra(i)})" for i, s in enumerate(SAFRAS, 1)}, True),
    ):
        lr = K.logrank(d, e, df[col])
        pares = K.logrank_pares_holm(d, e, df[col])
        for x in pares:
            x["rotulo_a"], x["rotulo_b"] = (rot or {}).get(x["a"], x["a"]), (rot or {}).get(x["b"], x["b"])
        out[nome] = {
            "logrank": {"chi2": lr["chi2"], "df": lr["df"], "p": lr["p"]},
            "grupos": _linhas_grupo(df, col, ordem, rot, safra=safra),
            "pares": pares,
            "n_pares": len(pares),
            "n_sig_bruto": int(sum(x["significativo_bruto"] for x in pares)),
            "n_sig_holm": int(sum(x["significativo_holm"] for x in pares)),
        }
    return out


# ------------------------------------------------------------------------------------
# Curvas pré-calculadas para o explorador interativo (canal x plano x safra)
# ------------------------------------------------------------------------------------

def explorador(df: pd.DataFrame, t_max: int = 24) -> dict:
    grade = np.arange(0, t_max + 1, dtype=float)
    canais = ["todos"] + list(C.CANAIS)
    planos = ["todos"] + list(C.PLANOS)
    safras = ["todas"] + list(SAFRAS)
    curvas = {}
    for c in canais:
        d1 = df if c == "todos" else df[df["canal"] == c]
        for p in planos:
            d2 = d1 if p == "todos" else d1[d1["plano"] == p]
            for s in safras:
                sub = d2 if s == "todas" else d2[d2["safra"] == s]
                n = len(sub)
                chave = f"{c}|{p}|{s}"
                if n == 0:
                    continue
                km = K.km_curve(sub["duracao_meses"], sub["evento"])
                S, lo, hi, nr = [], [], [], []
                for t in grade:
                    v, l, h = km.em(float(t))
                    S.append(round(v, 4)); lo.append(round(l, 4)); hi.append(round(h, 4))
                    nr.append(km.em_risco(float(t)))
                hz = {}
                for h in C.HORIZONTES:
                    pt = ponto(sub, h, safra_exige_completa=(s != "todas"))
                    hz[str(h)] = {"v": None if pt["valor"] is None else round(pt["valor"], 4),
                                  "lo": None if pt["lo"] is None else round(pt["lo"], 4),
                                  "hi": None if pt["hi"] is None else round(pt["hi"], 4),
                                  "nr": pt["n_risco"], "ok": pt["ok"], "motivo": pt["motivo"]}
                curvas[chave] = {"n": int(n), "ev": int(sub["evento"].sum()), "S": S, "lo": lo,
                                 "hi": hi, "nr": nr, "h": hz}
    return {
        "grade": [int(x) for x in grade],
        "canais": [{"chave": "todos", "rotulo": "Todos os canais"}] +
                  [{"chave": c, "rotulo": C.CANAIS_ROTULO[c]} for c in C.CANAIS],
        "planos": [{"chave": "todos", "rotulo": "Todos os planos"}] +
                  [{"chave": p, "rotulo": C.PLANOS_ROTULO[p]} for p in C.PLANOS],
        "safras": [{"chave": "todas", "rotulo": "Todas as safras"}] +
                  [{"chave": s, "rotulo": f"{s} · {rotulo_safra(i)}"} for i, s in enumerate(SAFRAS, 1)],
        "metas": {str(h): C.METAS[h] for h in C.HORIZONTES},
        "min_em_risco": C.MIN_EM_RISCO,
        "curvas": curvas,
    }
