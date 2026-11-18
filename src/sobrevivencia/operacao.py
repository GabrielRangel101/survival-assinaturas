"""Camada de operação de quem gere assinatura no dia a dia: ponte de MRR, retenção líquida de receita
(NRR/GRR), reativação, troca de plano (upgrade/downgrade) e conversão de trial.

A análise de sobrevivência olha o PRIMEIRO período de cada assinante e ignora reativações e trocas de plano
(isso está nos limites do relatório). Esta camada mostra o que essas simplificações escondem. Ela é gerada
com fluxos aleatórios INDEPENDENTES (``SeedSequence(SEED).spawn``, filhos 6 a 9), de modo que os tempos de
vida da análise principal não mudam. As taxas de reativação, troca de plano e conversão de trial são
PREMISSAS fictícias (config.py): aqui o objetivo é a mecânica de medir, não descobrir o mundo.

Convenções (todas declaradas no relatório):
* MRR de um assinante no fim de cada mês = preço pago naquele mês (tabela, com 60% de desconto nos 3 primeiros
  meses da Black Friday e o reajuste de jul/2026 para Mensal e Combo); o anual conta como preço mensal-equivalente.
* Quem entra e sai entre dois fins de mês não aparece na ponte (efeito pequeno).
* Cancelar e voltar dentro do mesmo mês não aparece como churn nem como reativação.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C
from . import value as V

_COMP = ("novo", "reativacao", "exp_upgrade", "exp_fim_promo", "exp_reajuste", "contracao", "churn")


# ------------------------------------------------------------------------------------
# Eventos: troca de plano e reativação
# ------------------------------------------------------------------------------------

def gerar_eventos(df: pd.DataFrame, seed: int = C.SEED) -> pd.DataFrame:
    """Acrescenta ao dataset: troca de plano, reativação e o segundo período (datas e plano)."""
    ss = np.random.SeedSequence(seed)
    filhos = ss.spawn(10)
    r_mud, r_reat, r_dur2 = (np.random.default_rng(filhos[i]) for i in (7, 8, 9))
    n = len(df)
    ini = df["data_inicio"].to_numpy("datetime64[D]")
    corte = np.datetime64(C.CORTE)
    fim1 = np.where(df["evento"].to_numpy() == 1,
                    df["data_cancelamento"].to_numpy("datetime64[D]"), corte + np.timedelta64(1, "D"))

    plano = df["plano"].to_numpy(object)
    # troca de plano: tempo exponencial; vale só se ocorre antes do fim do período
    destino = np.full(n, "", dtype=object)
    dias_troca = np.full(n, np.inf)
    u = r_mud.standard_exponential(n)
    for p, (dest, taxa) in C.MUDANCA_PLANO.items():
        m = plano == p
        destino[m] = dest
        dias_troca[m] = u[m] / taxa * C.DIAS_POR_MES
    data_troca = ini + np.where(np.isfinite(dias_troca), dias_troca, 1e9).astype("timedelta64[D]")
    troca = np.isfinite(dias_troca) & (data_troca < fim1) & (data_troca <= corte)
    out = df.copy()
    out["plano_troca"] = np.where(troca, destino, "")
    out["data_troca_plano"] = pd.to_datetime(np.where(troca, data_troca, np.datetime64("NaT")))
    plano_final = np.where(troca, destino, plano)

    # reativação (apenas de quem cancelou)
    cancel = df["evento"].to_numpy() == 1
    causa = df["causa"].to_numpy(object)
    p_r = np.array([C.REATIVA_PROB.get(c, 0.0) for c in causa])
    atraso_med = np.array([C.REATIVA_ATRASO_DIAS.get(c, 1.0) for c in causa])
    volta = cancel & (r_reat.random(n) < p_r)
    atraso = np.ceil(r_reat.standard_exponential(n) * atraso_med).astype(int) + 1
    ini2 = fim1 + atraso.astype("timedelta64[D]")
    volta &= ini2 <= corte
    dur2 = r_dur2.standard_exponential(n) / C.REATIVA_RISCO_MENSAL * C.DIAS_POR_MES
    fim2 = ini2 + np.ceil(dur2).astype("timedelta64[D]")
    cancela2 = volta & (fim2 <= corte)
    out["reativou"] = volta.astype(int)
    out["data_reativacao"] = pd.to_datetime(np.where(volta, ini2, np.datetime64("NaT")))
    out["data_cancelamento2"] = pd.to_datetime(np.where(cancela2, fim2, np.datetime64("NaT")))
    out["plano_reativacao"] = np.where(volta, plano_final, "")
    return out


# ------------------------------------------------------------------------------------
# Matrizes mensais
# ------------------------------------------------------------------------------------

def fins_de_mes() -> pd.DatetimeIndex:
    return pd.date_range(C.ENTRADA_INI, C.CORTE, freq="ME")


def _preco_lista(plano_idx: np.ndarray, reaj: np.ndarray) -> np.ndarray:
    """Preço de tabela por (plano, reajustado?). plano_idx: índice em C.PLANOS; -1 = inativo."""
    base = np.array([C.PRECO[p] for p in C.PLANOS] + [0.0])
    novo = np.array([C.PRECO_REAJUSTADO.get(p, C.PRECO[p]) for p in C.PLANOS] + [0.0])
    return np.where(reaj, novo[plano_idx], base[plano_idx])


def matrizes(ev: pd.DataFrame) -> dict:
    """Matrizes (assinantes x meses): ativo, plano, flag de promoção, flag de reajuste e MRR."""
    meses = fins_de_mes()
    e = meses.to_numpy("datetime64[D]")[None, :]
    n, T = len(ev), len(meses)
    ini = ev["data_inicio"].to_numpy("datetime64[D]")[:, None]
    fim1 = np.where(ev["evento"].to_numpy()[:, None] == 1,
                    ev["data_cancelamento"].to_numpy("datetime64[D]")[:, None],
                    np.datetime64(C.CORTE) + np.timedelta64(1, "D"))
    ativo1 = (ini <= e) & (e < fim1)
    ini2 = ev["data_reativacao"].to_numpy("datetime64[D]")[:, None]
    fim2 = np.where(ev["data_cancelamento2"].isna().to_numpy()[:, None],
                    np.datetime64(C.CORTE) + np.timedelta64(1, "D"),
                    ev["data_cancelamento2"].to_numpy("datetime64[D]")[:, None])
    reat = (ev["reativou"].to_numpy()[:, None] == 1)
    ativo2 = reat & (ini2 <= e) & (e < fim2)
    ativo = ativo1 | ativo2

    pidx = {p: i for i, p in enumerate(C.PLANOS)}
    entrada = np.array([pidx[p] for p in ev["plano"]])
    troca = ev["plano_troca"].to_numpy(object)
    destino = np.array([pidx[p] if p else -1 for p in troca])
    dt_troca = ev["data_troca_plano"].to_numpy("datetime64[D]")[:, None]
    apos_troca = (destino[:, None] >= 0) & (e >= dt_troca)
    plano1 = np.where(apos_troca, destino[:, None], entrada[:, None])
    plano_final = np.where(destino >= 0, destino, entrada)[:, None]
    plano = np.where(ativo1, plano1, np.where(ativo2, plano_final, len(C.PLANOS)))

    idade = (e - ini).astype("timedelta64[D]").astype(float) / C.DIAS_POR_MES
    promo = ativo1 & (ev["oferta_entrada"].to_numpy()[:, None] == "black_friday") & (idade < C.PROMO_MESES)
    reaj = np.broadcast_to(e >= np.datetime64(C.REAJUSTE_INI), (n, T))
    preco_base = _preco_lista(plano, reaj)
    mrr = np.where(ativo, preco_base * np.where(promo, 1.0 - C.PROMO_DESCONTO, 1.0), 0.0)
    return {"meses": meses, "ativo": ativo, "plano": plano, "promo": promo, "reaj": np.asarray(reaj),
            "mrr": mrr}


def _preco(plano_idx: np.ndarray, promo: np.ndarray, reaj: np.ndarray) -> np.ndarray:
    return _preco_lista(plano_idx, reaj) * np.where(promo, 1.0 - C.PROMO_DESCONTO, 1.0)


# ------------------------------------------------------------------------------------
# Ponte de MRR
# ------------------------------------------------------------------------------------

def ponte_mrr(M: dict) -> list[dict]:
    """Ponte mensal: inicial + novo + reativação + expansão − contração − churn = final."""
    ativo, plano, promo, reaj, mrr = M["ativo"], M["plano"], M["promo"], M["reaj"], M["mrr"]
    n, T = mrr.shape
    primeiro = np.where(ativo.any(axis=1), ativo.argmax(axis=1), -1)
    linhas = []
    for t in range(T):
        lin = {"mes": str(M["meses"][t].date())[:7], "inicial": 0.0 if t == 0 else float(mrr[:, t - 1].sum()),
               "ativos": int(ativo[:, t].sum()), "final": float(mrr[:, t].sum())}
        for k in _COMP:
            lin[k] = 0.0
        if t == 0:
            lin["novo"] = lin["final"]
        else:
            a0, a1 = ativo[:, t - 1], ativo[:, t]
            lin["novo"] = float(mrr[(~a0) & a1 & (primeiro == t), t].sum())
            lin["reativacao"] = float(mrr[(~a0) & a1 & (primeiro < t), t].sum())
            lin["churn"] = -float(mrr[a0 & ~a1, t - 1].sum())
            ambos = a0 & a1
            p0 = mrr[:, t - 1]
            pa = _preco(plano[:, t], promo[:, t - 1], reaj[:, t - 1])
            pb = _preco(plano[:, t], promo[:, t], reaj[:, t - 1])
            pc = _preco(plano[:, t], promo[:, t], reaj[:, t])
            d_plano = np.where(ambos, pa - p0, 0.0)
            lin["exp_upgrade"] = float(d_plano[d_plano > 0].sum())
            lin["contracao"] = float(d_plano[d_plano < 0].sum())
            lin["exp_fim_promo"] = float(np.where(ambos, pb - pa, 0.0).sum())
            lin["exp_reajuste"] = float(np.where(ambos, pc - pb, 0.0).sum())
        lin["ativos_inicio"] = 0 if t == 0 else int(ativo[:, t - 1].sum())
        lin["churn_logos"] = 0 if t == 0 else int((ativo[:, t - 1] & ~ativo[:, t]).sum())
        soma = lin["inicial"] + sum(lin[k] for k in _COMP)
        lin["confere"] = bool(abs(soma - lin["final"]) < 1e-6 * max(1.0, lin["final"]))
        linhas.append({k: (round(v, 2) if isinstance(v, float) else v) for k, v in lin.items()})
    return linhas


# ------------------------------------------------------------------------------------
# Retenção líquida de receita
# ------------------------------------------------------------------------------------

def _nrr_grr(m0: np.ndarray, m1: np.ndarray) -> tuple[float, float]:
    base = m0.sum()
    return float(m1.sum() / base), float(np.minimum(m1, m0).sum() / base)


def retencao_receita(M: dict, ev: pd.DataFrame, n_boot: int = C.N_BOOT_OPERACAO, seed: int = C.SEED + 3000) -> dict:
    """NRR e GRR em JANELA_NRR_MESES, para a base ativa no mês t-12 (último mês observado)."""
    T = M["mrr"].shape[1]
    t1, t0 = T - 1, T - 1 - C.JANELA_NRR_MESES
    base = M["ativo"][:, t0]
    m0 = M["mrr"][:, t0]
    m1 = M["mrr"][:, t1]
    rng = np.random.default_rng(seed)

    def estima(sel: np.ndarray) -> dict:
        idx = np.where(sel)[0]
        nrr, grr = _nrr_grr(m0[idx], m1[idx])
        bn, bg = np.empty(n_boot), np.empty(n_boot)
        for b in range(n_boot):
            j = idx[rng.integers(0, len(idx), len(idx))]
            bn[b], bg[b] = _nrr_grr(m0[j], m1[j])
        lo_n, hi_n = np.percentile(bn, [2.5, 97.5])
        lo_g, hi_g = np.percentile(bg, [2.5, 97.5])
        return {"n": int(len(idx)), "mrr_base": float(m0[idx].sum()), "nrr": nrr, "nrr_lo": float(lo_n),
                "nrr_hi": float(hi_n), "grr": grr, "grr_lo": float(lo_g), "grr_hi": float(hi_g),
                "expansao": float(nrr - grr)}   # quanto da receita da base a expansão recupera

    out = {"mes_base": str(M["meses"][t0].date())[:7], "mes_fim": str(M["meses"][t1].date())[:7],
           "global": estima(base), "por_canal": {}, "por_plano": {}}
    for c in C.CANAIS:
        out["por_canal"][c] = estima(base & (ev["canal"].to_numpy() == c))
    for p in C.PLANOS:
        out["por_plano"][p] = estima(base & (ev["plano"].to_numpy() == p))
    return out


# ------------------------------------------------------------------------------------
# Reativação, troca de plano e trial
# ------------------------------------------------------------------------------------

def reativacao(ev: pd.DataFrame, M: dict) -> dict:
    """Taxa de volta em até 12 meses por causa (entre quem cancelou há mais de 12 meses) e o efeito sobre a retenção."""
    corte = pd.Timestamp(C.CORTE)
    canc = ev[(ev["evento"] == 1) & (ev["data_cancelamento"] <= corte - pd.Timedelta(days=365))]
    por_causa = {}
    for c in C.CAUSAS:
        s = canc[canc["causa"] == c]
        if len(s) == 0:
            continue
        volta12 = ((s["reativou"] == 1)
                   & ((s["data_reativacao"] - s["data_cancelamento"]).dt.days <= 365))
        por_causa[c] = {"n_cancelaram": int(len(s)), "n_voltaram": int(volta12.sum()), "taxa": float(volta12.mean())}
    # retenção em 12 meses: primeiro período (KM-like, só elegíveis) x qualquer período
    el = ev[ev["seguimento_max_meses"] >= 12]
    fim12 = el["data_inicio"] + pd.to_timedelta(12 * C.DIAS_POR_MES, unit="D")
    ativo1 = (el["duracao_meses"] >= 12)
    ativo2 = ((el["reativou"] == 1) & (el["data_reativacao"] <= fim12)
              & (el["data_cancelamento2"].isna() | (el["data_cancelamento2"] > fim12)))
    n_el = len(el)
    return {
        "por_causa": por_causa,
        "n_cancelamentos_total": int((ev["evento"] == 1).sum()),
        "n_reativacoes_total": int(ev["reativou"].sum()),
        "pct_cancelados_que_voltaram": float(ev["reativou"].sum() / max((ev["evento"] == 1).sum(), 1)),
        "retencao_m12_primeiro_periodo": float(ativo1.mean()),
        "retencao_m12_com_reativacao": float((ativo1 | ativo2).mean()),
        "n_elegiveis_m12": int(n_el),
        "ganho_retencao_m12": float((ativo1 | ativo2).mean() - ativo1.mean()),
    }


def trocas_de_plano(ev: pd.DataFrame) -> dict:
    t = ev[ev["plano_troca"] != ""]
    pares = {}
    for (a, b), s in t.groupby(["plano", "plano_troca"]):
        pares[f"{a}>{b}"] = {"origem": a, "destino": b, "n": int(len(s)),
                             "delta_preco": float(C.PRECO_REAJUSTADO.get(b, C.PRECO[b]) - C.PRECO_REAJUSTADO.get(a, C.PRECO[a]))}
    return {"n_trocas": int(len(t)), "pct_assinantes": float(len(t) / len(ev)), "pares": pares}


def _wilson(k: int, n: int) -> tuple[float, float]:
    z = C.Z95
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return float(c - h), float(c + h)


def funil_trial(ev: pd.DataFrame, seed: int = C.SEED) -> dict:
    """Conversão de trial por canal. Os trials que NÃO converteram não estão no dataset: são sorteados
    por uma binomial negativa (número de fracassos antes de n sucessos com a conversão plantada)."""
    r = np.random.default_rng(np.random.SeedSequence(seed).spawn(10)[6])
    linhas = []
    tot_t = tot_c = 0
    for c in C.CANAIS:
        conv = int((ev["canal"] == c).sum())
        falhas = int(r.negative_binomial(conv, C.TRIAL_CONVERSAO[c]))
        trials = conv + falhas
        lo, hi = _wilson(conv, trials)
        tot_t += trials
        tot_c += conv
        linhas.append({"canal": c, "rotulo": C.CANAIS_ROTULO[c], "trials": trials, "convertidos": conv,
                       "conversao": conv / trials, "lo": lo, "hi": hi, "plantada": C.TRIAL_CONVERSAO[c],
                       "cac": C.CAC[c], "cac_por_trial": C.CAC[c] * conv / trials})
    lo, hi = _wilson(tot_c, tot_t)
    return {"canais": linhas, "global": {"trials": tot_t, "convertidos": tot_c, "conversao": tot_c / tot_t,
                                         "lo": lo, "hi": hi}}


# ------------------------------------------------------------------------------------
# Orquestração
# ------------------------------------------------------------------------------------

def analise(df: pd.DataFrame, n_boot: int = C.N_BOOT_OPERACAO) -> dict:
    ev = gerar_eventos(df)
    M = matrizes(ev)
    ponte = ponte_mrr(M)
    ult = ponte[-12:]
    soma = {k: float(sum(x[k] for x in ult)) for k in _COMP}
    ini12 = ult[0]["inicial"]
    fim12 = ult[-1]["final"]
    nrr = retencao_receita(M, ev, n_boot)
    churn_logo_12m = float(np.mean([x["churn_logos"] / x["ativos_inicio"] for x in ult if x["ativos_inicio"] > 0]))
    churn_mrr_12m = float(np.mean([-x["churn"] / x["inicial"] for x in ult if x["inicial"] > 0]))
    return {
        "convencoes": {"meses": int(len(ponte)), "mrr_inclui_promocao_e_reajuste": True},
        "ponte": ponte,
        "ultimos_12m": {"inicial": ini12, "final": fim12, "crescimento": float(fim12 / ini12 - 1.0), **soma,
                        "churn_logo_mensal_medio": churn_logo_12m, "churn_mrr_mensal_medio": churn_mrr_12m,
                        "expansao_total": soma["exp_upgrade"] + soma["exp_fim_promo"] + soma["exp_reajuste"]},
        "mrr_final": fim12, "ativos_final": int(ponte[-1]["ativos"]),
        "arpu_final": float(fim12 / max(ponte[-1]["ativos"], 1)),
        "retencao_receita": nrr,
        "reativacao": reativacao(ev, M),
        "trocas_plano": trocas_de_plano(ev),
        "trial": funil_trial(ev),
        "premissas": {"trial": dict(C.TRIAL_CONVERSAO), "reativa_prob": dict(C.REATIVA_PROB),
                      "reativa_atraso_dias": dict(C.REATIVA_ATRASO_DIAS),
                      "reativa_risco_mensal": C.REATIVA_RISCO_MENSAL,
                      "mudanca_plano": {p: {"destino": d, "taxa_mensal": r} for p, (d, r) in C.MUDANCA_PLANO.items()},
                      "janela_nrr_meses": C.JANELA_NRR_MESES},
        "ponte_confere": bool(all(x["confere"] for x in ponte)),
    }
