"""F. O que poderia ter dado errado: censura ignorada, riscos proporcionais violados, ranking por
M12 bruto com safra pequena. Cada armadilha é quantificada contra a verdade plantada."""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C
from . import km as K


def censura_ignorada(df: pd.DataFrame, gt: dict, h: int = 12) -> dict:
    """Quatro jeitos de calcular a retenção em M12 de toda a base, três deles errados."""
    dur, ev = df["duracao_meses"].to_numpy(), df["evento"].to_numpy()
    verdade = gt["sobrevivencia_verdade"]["global"][f"m{h}"]["todos"]
    kmp = K.km_ponto(dur, ev, h)
    ativos_sobre_iniciados = float((ev == 0).mean())
    censura_como_cancelamento = float((dur >= h).mean())
    conhecido = ((ev == 1) & (dur < h)) | (dur >= h)  # status em h conhecido
    descartar_censurados = float((dur[conhecido] >= h).mean())
    metodos = [
        {"id": "ativos_sobre_iniciados", "rotulo": "Ativos hoje ÷ iniciados (ignora o tempo de casa)",
         "valor": ativos_sobre_iniciados},
        {"id": "censura_como_cancelamento", "rotulo": "Tratar censurado como cancelado",
         "valor": censura_como_cancelamento},
        {"id": "descartar_censurados", "rotulo": "Descartar quem foi censurado antes de M12",
         "valor": descartar_censurados},
        {"id": "kaplan_meier", "rotulo": "Kaplan-Meier (usa a censura corretamente)", "valor": kmp["valor"],
         "lo": kmp["lo"], "hi": kmp["hi"]},
    ]
    for m in metodos:
        m["erro_pp"] = float(m["valor"] - verdade)
    return {"horizonte": h, "verdade": float(verdade), "metodos": metodos}


def ph_violada(df: pd.DataFrame, hr_ingenuo_bf: float, tab_corrigida: list[dict],
               p_faixas_bf: float, p_rank_bf: float) -> dict:
    """O HR único da promoção esconde o penhasco: compara o previsto com o observado no mês 3–4."""
    hr = {r["nome"]: r for r in tab_corrigida}
    na = df[df["plano"] != "anual"]
    base = na[na["oferta_entrada"] == "nenhuma"]
    bf = na[na["oferta_entrada"] == "black_friday"]
    q0 = K.prob_condicional(base["duracao_meses"], base["evento"], 3.0, 4.0)["prob"]
    q_obs = K.prob_condicional(bf["duracao_meses"], bf["evento"], 3.0, 4.0)["prob"]
    q_naive = 1 - (1 - q0) ** hr_ingenuo_bf
    q_corr = 1 - (1 - q0) ** hr["promo_penhasco"]["hr"]
    return {
        "hr_unico_ingenuo": float(hr_ingenuo_bf),
        "p_rank_ingenuo": float(p_rank_bf), "p_faixas_ingenuo": float(p_faixas_bf),
        "hr_periodos": {k: {"hr": hr[k]["hr"], "lo": hr[k]["lo"], "hi": hr[k]["hi"],
                            "verdade": hr[k]["verdade"]}
                        for k in ("promo_vigente", "promo_penhasco", "promo_pos")},
        "q_base_mes3": float(q0), "q_observado_bf_mes3": float(q_obs),
        "q_previsto_ingenuo": float(q_naive), "q_previsto_corrigido": float(q_corr),
        "subestimacao_ingenua": float(q_obs / q_naive - 1.0),
        "n_bf_risco_mes3": int(K.prob_condicional(bf["duracao_meses"], bf["evento"], 3.0, 4.0)["n_risco"]),
    }


def ranking_m12_bruto(df: pd.DataFrame, gt: dict, n_sorteios: int = C.N_SORTEIOS_RANKING,
                      tamanho: int = C.TAMANHO_SAFRA_PEQUENA, seed: int = C.SEED + 2000) -> dict:
    """Quão confiável é ranquear canais pelo M12 bruto numa safra pequena?

    Entre elegíveis (todos com >= 12 meses possíveis) sorteamos subamostras do tamanho de uma
    "safra pequena" e vemos com que frequência o ranking bruto acerta o melhor e o pior canal."""
    rng = np.random.default_rng(seed)
    el = df[df["seguimento_max_meses"] >= 12].reset_index(drop=True)
    vivo = (el["duracao_meses"] >= 12).to_numpy().astype(float)
    canal = el["canal"].to_numpy()
    verdade = {c: gt["sobrevivencia_verdade"]["por_canal"][c]["m12"]["todos"] for c in C.CANAIS}
    top_v = max(verdade, key=verdade.get)
    bot_v = min(verdade, key=verdade.get)
    acerta_top = acerta_bot = 0
    erros = []
    larguras = []
    n_min = []
    for _ in range(n_sorteios):
        i = rng.choice(len(el), size=tamanho, replace=False)
        est = {}
        ns = {}
        for c in C.CANAIS:
            m = canal[i] == c
            ns[c] = int(m.sum())
            est[c] = float(vivo[i][m].mean()) if m.sum() > 0 else np.nan
            if m.sum() > 0:
                p = est[c]
                larguras.append(2 * 1.96 * np.sqrt(max(p * (1 - p), 1e-9) / m.sum()))
                erros.append(abs(p - verdade[c]))
        validos = {c: v for c, v in est.items() if not np.isnan(v)}
        acerta_top += int(max(validos, key=validos.get) == top_v)
        acerta_bot += int(min(validos, key=validos.get) == bot_v)
        n_min.append(min(ns.values()))
    # exemplo real: ranking bruto por safra completa em M12
    safras = []
    for s in ("S1", "S2", "S3", "S4"):
        sub = df[(df["safra"] == s)]
        v = sub["duracao_meses"] >= 12
        por = {c: (float(v[sub["canal"] == c].mean()), int((sub["canal"] == c).sum())) for c in C.CANAIS}
        safras.append({"safra": s, "melhor": max(por, key=lambda c: por[c][0]),
                       "pior": min(por, key=lambda c: por[c][0]),
                       "n_menor_celula": min(v[1] for v in por.values())})
    return {
        "tamanho_safra_pequena": tamanho, "n_sorteios": n_sorteios, "n_elegiveis": int(len(el)),
        "melhor_verdadeiro": top_v, "pior_verdadeiro": bot_v,
        "p_acerta_melhor": acerta_top / n_sorteios, "p_acerta_pior": acerta_bot / n_sorteios,
        "erro_abs_medio_pp": float(np.mean(erros)), "largura_media_ic": float(np.mean(larguras)),
        "n_mediano_menor_canal": float(np.median(n_min)),
        "safras_reais": safras,
    }
