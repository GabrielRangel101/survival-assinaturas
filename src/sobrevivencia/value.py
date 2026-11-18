"""Valor por canal (RMST, LTV descontado, payback, bootstrap) e decisão em R$.

Separamos MEDIDO de PROJETADO:
* medido: parte da curva em que há assinantes suficientes sob risco (KM observado);
* projetado: cauda além do suporte, extrapolada com risco constante (média da janela final).
ARPU, margem, CAC, taxa de desconto e a efetividade da ação do mês 3 são PREMISSAS (config.py).
O LTV é de CONTRIBUIÇÃO (receita x margem por real), e o CAC entra com incerteza (±CAC_INCERTEZA).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C
from . import km as K

H = C.HORIZONTE_LTV


def preco_vigente(plano: str) -> float:
    """Preço de tabela vigente (pós-reajuste de jul/2026) do plano."""
    return float(C.PRECO_REAJUSTADO.get(plano, C.PRECO[plano]))


def preco_por_idade(df: pd.DataFrame, horizonte: int = H) -> np.ndarray:
    """Preço pago por mês de vida m = 0..H-1 (R$): tabela VIGENTE; BF: 60% off nos 3 primeiros."""
    base = df["plano"].map({p: preco_vigente(p) for p in C.PLANOS}).to_numpy(float)
    P = np.tile(base[:, None], (1, horizonte))
    bf = (df["oferta_entrada"] == "black_friday").to_numpy()
    P[bf, : C.PROMO_MESES] *= 1.0 - C.PROMO_DESCONTO
    return P


def fator_desconto(horizonte: int = H) -> np.ndarray:
    return (1.0 + C.TAXA_DESCONTO_ANUAL) ** (-np.arange(horizonte) / 12.0)


def curva_mensal(duracao, evento, horizonte: int = H, min_risco: int = C.MIN_EM_RISCO,
                 janela: float = 6.0) -> dict:
    """S(m), m = 0..H: KM no suporte (n em risco >= min_risco); além disso, risco constante."""
    km = K.km_curve(duracao, evento)
    ord_ = km.dur_ord
    t_sup = float(ord_[-min_risco]) if len(ord_) >= min_risco else 0.0
    t_sup = min(t_sup, float(horizonte))
    grade = np.arange(0, horizonte + 1, dtype=float)
    S = km.em_varios(grade).astype(float)
    lam = 0.0
    s_sup = float(km.em(t_sup)[0])
    if t_sup < horizonte:
        j = min(janela, t_sup)
        s_ant = float(km.em(t_sup - j)[0])
        if j > 0 and s_ant > 0 and s_sup < s_ant:
            lam = -np.log(s_sup / s_ant) / j
        proj = grade > t_sup
        S[proj] = s_sup * np.exp(-lam * (grade[proj] - t_sup))
    return {"S": S, "medido": grade <= t_sup, "t_sup": t_sup, "lambda": float(lam),
            "s_sup": s_sup, "km": km}


def avaliar(duracao, evento, P: np.ndarray, cac: float, horizonte: int = H) -> dict:
    """RMST, LTV descontado e payback de um grupo (todas as grandezas esperadas por assinante)."""
    cv = curva_mensal(duracao, evento, horizonte)
    S, t_sup, lam, km = cv["S"], cv["t_sup"], cv["lambda"], cv["km"]
    arpu = P.mean(axis=0)
    termos_rec = arpu * S[:horizonte] * fator_desconto(horizonte)
    termos = termos_rec * C.MARGEM_POR_REAL  # contribuição
    med = cv["medido"][:horizonte]
    ltv_med, ltv_proj = float(termos[med].sum()), float(termos[~med].sum())
    # RMST(H): KM até o suporte + cauda exponencial analítica
    rmst_med = K.rmst(km, min(t_sup, horizonte))
    L = horizonte - t_sup
    rmst_proj = 0.0
    if L > 0:
        rmst_proj = cv["s_sup"] * (1 - np.exp(-lam * L)) / lam if lam > 1e-12 else cv["s_sup"] * L
    acum = np.cumsum(termos)
    ok = np.where(acum >= cac)[0]
    payback = float(ok[0] + 1) if len(ok) else float(horizonte + 1)
    ltv = ltv_med + ltv_proj
    return {"rmst": rmst_med + rmst_proj, "rmst_medido": float(rmst_med), "rmst_proj": float(rmst_proj),
            "ltv": ltv, "ltv_medido": ltv_med, "ltv_proj": ltv_proj, "ltv_receita": float(termos_rec.sum()),
            "ltv_cac": ltv / cac, "payback": payback, "t_sup": t_sup, "arpu_medio": float(arpu[0]),
            "s": {f"m{h}": float(S[h]) for h in C.HORIZONTES},
            "acum": acum, "S": S}


def _ic(x: np.ndarray) -> tuple[float, float]:
    lo, hi = np.percentile(x, [2.5, 97.5])
    return float(lo), float(hi)


def analise_valor(df: pd.DataFrame, n_boot: int = C.N_BOOT, seed: int = C.SEED + 1000) -> dict:
    """RMST/LTV/payback por canal, IC por bootstrap de assinantes (reamostra dentro de cada canal).

    O CAC é uma premissa: além do bootstrap, cada réplica sorteia um multiplicador de CAC em
    [1 - CAC_INCERTEZA, 1 + CAC_INCERTEZA] por canal, e as probabilidades e faixas de decisão
    contam as duas fontes de incerteza.
    """
    rng = np.random.default_rng(seed)
    rng_cac = np.random.default_rng(seed + 7)
    P_all = preco_por_idade(df)
    dur_all = df["duracao_meses"].to_numpy()
    ev_all = df["evento"].to_numpy()
    idx_canal = {c: np.where(df["canal"].to_numpy() == c)[0] for c in C.CANAIS}

    pontual = {}
    for c in C.CANAIS:
        i = idx_canal[c]
        pontual[c] = avaliar(dur_all[i], ev_all[i], P_all[i], C.CAC[c])

    chaves = ("rmst", "ltv", "ltv_receita", "ltv_medido", "ltv_proj", "ltv_cac", "payback", "rmst_medido", "rmst_proj")
    bs = {c: {k: np.empty(n_boot) for k in chaves} for c in C.CANAIS}
    for b in range(n_boot):
        for c in C.CANAIS:
            i = idx_canal[c]
            r = rng.integers(0, len(i), len(i))
            j = i[r]
            a = avaliar(dur_all[j], ev_all[j], P_all[j], C.CAC[c])
            for k in chaves:
                bs[c][k][b] = a[k]
    mult_cac = {c: rng_cac.uniform(1 - C.CAC_INCERTEZA, 1 + C.CAC_INCERTEZA, n_boot) for c in C.CANAIS}
    razao_inc = {c: bs[c]["ltv"] / (C.CAC[c] * mult_cac[c]) for c in C.CANAIS}   # LTV/CAC com as duas incertezas

    canais = []
    for c in C.CANAIS:
        p = pontual[c]
        d = {"canal": c, "rotulo": C.CANAIS_ROTULO[c], "n": int(len(idx_canal[c])), "cac": C.CAC[c],
             "arpu_inicial": p["arpu_medio"], "t_suporte_meses": p["t_sup"]}
        for k in ("rmst", "ltv", "ltv_receita", "ltv_medido", "ltv_proj", "ltv_cac", "payback", "rmst_medido", "rmst_proj"):
            lo, hi = _ic(bs[c][k])
            d[k] = {"est": float(p[k]), "lo": lo, "hi": hi}
        lo_i, hi_i = _ic(razao_inc[c])
        d["ltv_cac_incerteza"] = {"est": float(p["ltv_cac"]), "lo": lo_i, "hi": hi_i}
        d["ltv_liquido"] = {"est": float(p["ltv"] - C.CAC[c]), "lo": d["ltv"]["lo"] - C.CAC[c],
                            "hi": d["ltv"]["hi"] - C.CAC[c]}
        d["pct_ltv_medido"] = float(p["ltv_medido"] / p["ltv"])
        d["s"] = p["s"]
        d["payback_ate_24"] = bool(p["payback"] <= C.HORIZONTE_LTV)
        canais.append(d)

    # probabilidade de cada canal escalável ser o melhor (por réplica)
    esc = [c for c in C.CANAIS if c in C.CANAIS_ESCALAVEIS]
    ratio_fix = np.column_stack([bs[c]["ltv_cac"] for c in esc])
    ratio_inc = np.column_stack([razao_inc[c] for c in esc])
    liq = np.column_stack([bs[c]["ltv"] - C.CAC[c] * mult_cac[c] for c in esc])
    por_fix = np.bincount(ratio_fix.argmax(axis=1), minlength=len(esc)) / n_boot
    por_inc = np.bincount(ratio_inc.argmax(axis=1), minlength=len(esc)) / n_boot
    por_liq = np.bincount(liq.argmax(axis=1), minlength=len(esc)) / n_boot
    for d in canais:
        d["escalavel"] = d["canal"] in esc
        d["prob_melhor_ltv_cac_cac_fixo"] = None
        d["prob_melhor_ltv_cac"] = None
        d["prob_melhor_liquido"] = None
    for j, c in enumerate(esc):
        d = next(x for x in canais if x["canal"] == c)
        d["prob_melhor_ltv_cac_cac_fixo"] = float(por_fix[j])
        d["prob_melhor_ltv_cac"] = float(por_inc[j])       # bootstrap + incerteza de CAC
        d["prob_melhor_liquido"] = float(por_liq[j])

    # rankings entre os canais escaláveis (os que recebem verba) e geral
    rank_cac = sorted(esc, key=lambda c: C.CAC[c])
    rank_ratio = sorted(esc, key=lambda c: -pontual[c]["ltv_cac"])
    rank_ltv = sorted(esc, key=lambda c: -pontual[c]["ltv"])      # permanência pura: não depende do CAC
    rank_liq = sorted(esc, key=lambda c: -(pontual[c]["ltv"] - C.CAC[c]))
    rank_ratio_geral = sorted(C.CANAIS, key=lambda c: -pontual[c]["ltv_cac"])
    curvas = {c: {"acum": [round(float(x), 2) for x in pontual[c]["acum"]],
                  "S": [round(float(x), 4) for x in pontual[c]["S"]],
                  "t_sup": pontual[c]["t_sup"]} for c in C.CANAIS}

    # ---- sensibilidade ao CAC: o que precisaria mudar para o ranking virar ----
    melhor, segundo = rank_ratio[0], rank_ratio[1]
    r_melhor = pontual[melhor]["ltv_cac"]
    empate = {}
    for c in esc:
        if c == melhor:
            continue
        cac_emp = pontual[c]["ltv"] / r_melhor
        empate[c] = {"cac_empate": float(cac_emp), "cac_premissa": C.CAC[c],
                     "variacao": float(cac_emp / C.CAC[c] - 1.0), "queda": float(1.0 - cac_emp / C.CAC[c])}
    cac_melhor_perde = pontual[melhor]["ltv"] / pontual[segundo]["ltv_cac"]
    sens = {"melhor": melhor, "segundo": segundo, "empate": empate,
            "cac_melhor_perde_lideranca": float(cac_melhor_perde),
            "alta_cac_melhor_perde": float(cac_melhor_perde / C.CAC[melhor] - 1.0),
            "incerteza_cac": C.CAC_INCERTEZA}

    # ---- realocação: faixa de cenários de CAC marginal do canal que recebe a verba ----
    def cenarios(origem: str, destino: str) -> dict:
        r_o, r_d = pontual[origem]["ltv_cac"], pontual[destino]["ltv_cac"]
        linhas = []
        for prem in C.PREMIOS_CAC_MARGINAL:
            ponto = C.VERBA_EXEMPLO * (r_d / (1.0 + prem) - r_o)
            draws = C.VERBA_EXEMPLO * (razao_inc[destino] / (1.0 + prem) - razao_inc[origem])
            lo, hi = _ic(draws)
            linhas.append({"premio": float(prem), "ganho": float(ponto), "lo": lo, "hi": hi,
                           "prob_positivo": float((draws > 0).mean())})
        prem_eq = r_d / r_o - 1.0
        prem_draw = razao_inc[destino] / razao_inc[origem] - 1.0
        return {"origem": origem, "destino": destino, "linhas": linhas, "premio_equilibrio": float(prem_eq),
                "premio_equilibrio_lo": _ic(prem_draw)[0], "premio_equilibrio_hi": _ic(prem_draw)[1]}

    pior = rank_ratio[-1]
    realocacao = {"pior_para_melhor": cenarios(pior, melhor)}
    if "midia_paga" in esc and "midia_paga" not in (pior, melhor):
        realocacao["midia_para_melhor"] = cenarios("midia_paga", melhor)
    return {"canais": canais, "n_boot": int(n_boot), "ranking_cac": rank_cac,
            "ranking_ltv_cac": rank_ratio, "ranking_ltv": rank_ltv, "ranking_liquido": rank_liq,
            "ranking_ltv_cac_geral": rank_ratio_geral, "curvas": curvas,
            "rank_inverte": bool(rank_cac != rank_ratio), "sensibilidade_cac": sens,
            "realocacao": realocacao,
            "margem": {"contribuicao": C.MARGEM_CONTRIBUICAO, "cobranca": C.CUSTO_COBRANCA,
                       "por_real": C.MARGEM_POR_REAL}}


# ------------------------------------------------------------------------------------
# Decisão de verba e ação no mês 3 da promoção
# ------------------------------------------------------------------------------------

def decisao_verba(valor: dict) -> dict:
    """Retorno por R$ e realocação ilustrativa de VERBA_EXEMPLO como FAIXA de cenários (PROJETADO)."""
    por = {c["canal"]: c for c in valor["canais"]}
    linhas = []
    for c in C.CANAIS:
        v = por[c]
        n_aq = C.VERBA_EXEMPLO / C.CAC[c]
        linhas.append({
            "canal": c, "rotulo": C.CANAIS_ROTULO[c], "cac": C.CAC[c],
            "assinantes_por_verba": float(n_aq),
            "ltv_total": float(n_aq * v["ltv"]["est"]),
            "valor_liquido": float(n_aq * v["ltv_liquido"]["est"]),
            "retorno_por_real": float(v["ltv_cac"]["est"]),
        })
    for x in linhas:
        x["escalavel"] = x["canal"] in C.CANAIS_ESCALAVEIS
    esc = [x for x in linhas if x["escalavel"]]
    melhor = max(esc, key=lambda x: x["retorno_por_real"])
    pior = min(esc, key=lambda x: x["retorno_por_real"])
    mais_barato = min(esc, key=lambda x: x["cac"])
    return {
        "verba_exemplo": C.VERBA_EXEMPLO, "linhas": linhas,
        "melhor": melhor["canal"], "pior": pior["canal"], "mais_barato": mais_barato["canal"],
        "realocacao": valor["realocacao"],
        "sensibilidade": valor["sensibilidade_cac"],
    }


def acao_mes3(df: pd.DataFrame, tab_hr: list[dict]) -> dict:
    """Penhasco do mês 3: excesso de cancelamentos MEDIDO e valor da ação PROJETADO.

    Medido: probabilidade condicional observada de cancelar nos períodos pós-promoção (KM dos
    assinantes da Black Friday) e HR ajustado do Cox corrigido (penhasco e pós-penhasco).
    Contrafactual sem penhasco: q_cf = 1 - (1 - q_obs)^(1/HR) (risco proporcional dentro do período).
    Projetado: valor presente do que seria retido, para uma coorte de referência, e o líquido da ação.
    """
    hr = {r["nome"]: r for r in tab_hr}
    bf = df[df["oferta_entrada"] == "black_friday"]
    km = K.km_curve(bf["duracao_meses"], bf["evento"])
    s3, s4, s6 = km.em(3.0)[0], km.em(4.0)[0], km.em(6.0)[0]
    q_pen = 1 - s4 / s3
    q_pos = 1 - s6 / s4

    def excesso(q_obs: float, h: float) -> float:
        return float(q_obs - (1 - (1 - q_obs) ** (1.0 / h)))

    ex = {}
    for nome, q in (("promo_penhasco", q_pen), ("promo_pos", q_pos)):
        r = hr[nome]
        ex[nome] = {"q_obs": float(q), "hr": r["hr"], "hr_lo": r["lo"], "hr_hi": r["hi"],
                    "excesso": excesso(q, r["hr"]), "excesso_lo": excesso(q, r["lo"]),
                    "excesso_hi": excesso(q, r["hi"])}
    ini_ref, fim_ref, _ = C.CAMPANHAS[C.ACAO_COORTE_REFERENCIA]
    ref = df[(df["oferta_entrada"] == "black_friday")
             & df["data_inicio"].between(pd.Timestamp(ini_ref), pd.Timestamp(fim_ref))]
    n_ref = int(len(ref))
    vivos3 = n_ref * float(s3)
    vivos4 = vivos3 * (1 - q_pen)
    exc_pen = vivos3 * ex["promo_penhasco"]["excesso"]
    exc_pos = vivos4 * ex["promo_pos"]["excesso"]

    # valor de um assinante retido: contribuição dos pagamentos a preço cheio vigente dos meses 4.. (PV em m=3)
    cv = curva_mensal(bf["duracao_meses"], bf["evento"], H)
    preco_cheio = float(bf["plano"].map({p: preco_vigente(p) for p in C.PLANOS}).mean())
    m = np.arange(4, H)
    cond = cv["S"][m] / cv["S"][4]
    v_ret = float(np.sum(preco_cheio * cond * (1.0 + C.TAXA_DESCONTO_ANUAL) ** (-(m - 3) / 12.0))
                  * C.MARGEM_POR_REAL)  # valor de CONTRIBUIÇÃO do assinante retido
    perdido = float(exc_pen * v_ret)  # valor do excesso no penhasco (mês 3–4); pós-penhasco não monetizado
    custo = float(C.ACAO_CUSTO_POR_ASSINANTE * vivos3)
    cenarios = []
    for e in C.ACAO_EFETIVIDADES:
        ben = float(e * perdido)
        cenarios.append({"efetividade": e, "beneficio": ben, "custo": custo, "liquido": ben - custo})
    base = next(x for x in cenarios if abs(x["efetividade"] - C.ACAO_EFETIVIDADE_BASE) < 1e-9)
    return {
        "medido": {"s3": float(s3), "s4": float(s4), "q_penhasco": float(q_pen), "q_pos": float(q_pos),
                   "periodos": ex, "n_bf_total": int(len(bf)), "bf_eventos": int(bf["evento"].sum())},
        "projetado": {
            "coorte_referencia": C.ACAO_COORTE_REFERENCIA, "n_coorte": n_ref, "vivos_mes3": float(vivos3),
            "cancelamentos_em_excesso_penhasco": float(exc_pen),
            "cancelamentos_em_excesso_pos": float(exc_pos),
            "valor_assinante_retido": v_ret, "preco_cheio_medio": preco_cheio,
            "valor_perdido_penhasco": perdido,
            "custo_acao": custo, "custo_por_assinante": C.ACAO_CUSTO_POR_ASSINANTE,
            "efetividade_base": C.ACAO_EFETIVIDADE_BASE, "cenarios": cenarios, "base": base,
            "efetividade_equilibrio": float(custo / perdido) if perdido > 0 else None,
        },
    }
