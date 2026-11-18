"""Orquestra a análise A–H e grava results.json (FONTE ÚNICA dos números dos documentos)."""

from __future__ import annotations

import json
import platform
import re
import time
from importlib import metadata

import numpy as np
import pandas as pd

from . import cohorts as H
from . import competing as G
from . import config as C
from . import cox as X
from . import pitfalls as P
from . import simulate as S
from . import value as V


# ------------------------------------------------------------------------------------
# Serialização
# ------------------------------------------------------------------------------------

def _limpa(o):
    """Converte tipos numpy e NaN/inf para JSON puro."""
    if isinstance(o, dict):
        return {str(k): _limpa(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_limpa(v) for v in o]
    if isinstance(o, np.ndarray):
        return [_limpa(v) for v in o.tolist()]
    if isinstance(o, (np.floating, float)):
        f = float(o)
        return f if np.isfinite(f) else None
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, (pd.Timestamp,)):
        return str(o.date())
    return o


def serializar(res: dict) -> str:
    txt = json.dumps(_limpa(res), indent=1, ensure_ascii=False)
    # arrays de escalares em uma linha só (arquivo legível e menor)
    return re.sub(r"\[\s+([^\[\]{}]*?)\s+\]", lambda m: "[" + re.sub(r"\s+", " ", m.group(1)) + "]", txt)


# ------------------------------------------------------------------------------------
# Blocos
# ------------------------------------------------------------------------------------

def contar_testes() -> int | None:
    """Número de testes pytest coletados (para citar nos documentos); None se indisponível."""
    import subprocess
    import sys
    try:
        r = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "tests"], cwd=str(C.RAIZ),
                           capture_output=True, text=True, timeout=300)
        txt = r.stdout + r.stderr
        m = re.search(r"(\d+)\s+tests?\s+collected", txt)
        if m:
            return int(m.group(1))
        por_arquivo = re.findall(r"^tests[/\]\S+\.py:\s*(\d+)\s*$", txt, flags=re.M)  # formato -qq
        return int(sum(int(x) for x in por_arquivo)) if por_arquivo else None
    except Exception:  # noqa: BLE001
        return None


def _versoes() -> dict:
    out = {"python": platform.python_version()}
    for pkg in ("numpy", "pandas", "scipy", "lifelines", "statsmodels", "matplotlib"):
        out[pkg] = metadata.version(pkg)
    return out


def _premissas(n_boot: int) -> dict:
    return {
        "seed": C.SEED, "n": C.N_ASSINANTES,
        "entrada_ini": str(C.ENTRADA_INI), "entrada_fim": str(C.ENTRADA_FIM), "corte": str(C.CORTE),
        "alpha": C.ALPHA, "nivel_ic": 1 - C.ALPHA, "dias_por_mes": C.DIAS_POR_MES, "min_em_risco": C.MIN_EM_RISCO,
        "horizontes": list(C.HORIZONTES), "metas": {f"m{h}": C.METAS[h] for h in C.HORIZONTES},
        "risco_mensal_base": C.HAZARD_BASE,
        "promo": {"desconto": C.PROMO_DESCONTO, "meses": C.PROMO_MESES},
        "cac": dict(C.CAC), "canais_escalaveis": list(C.CANAIS_ESCALAVEIS),
        "preco": dict(C.PRECO), "taxa_desconto_anual": C.TAXA_DESCONTO_ANUAL,
        "horizonte_ltv": C.HORIZONTE_LTV, "verba_exemplo": C.VERBA_EXEMPLO,
        "acao": {"efetividades": list(C.ACAO_EFETIVIDADES), "efetividade_base": C.ACAO_EFETIVIDADE_BASE,
                 "custo_por_assinante": C.ACAO_CUSTO_POR_ASSINANTE},
        "n_boot": n_boot, "n_sorteios_ranking": C.N_SORTEIOS_RANKING,
        "tamanho_safra_pequena": C.TAMANHO_SAFRA_PEQUENA,
        "n_safras": C.N_SAFRAS, "meses_por_safra": C.MESES_POR_SAFRA,
        "reajuste": {"ini": str(C.REAJUSTE_INI), "fim": str(C.REAJUSTE_FIM),
                     "preco_mensal": C.PRECO_REAJUSTADO["mensal"], "preco_combo": C.PRECO_REAJUSTADO["combo"]},
        "hr_plantado": {
            "canal": {c: C.HR_CANAL[c] for c in C.CANAIS if c != C.CANAL_REF},
            "engajamento_por_dp": C.HR_ENGAJ_POR_DP, "passe_copa": C.HR_PASSE_COPA,
            "reajuste": C.HR_REAJUSTE,
            "promo": {k: v["hr"] for k, v in C.HR_PROMO_PERIODOS.items()},
            "plano": {p: C.HR_PLANO[p] for p in C.HR_PLANO if p != C.PLANO_REF},
        },
        "rotulos": {"canal": C.CANAIS_ROTULO, "plano": C.PLANOS_ROTULO, "causa": C.CAUSAS_ROTULO,
                    "safra": {s: S.rotulo_safra(i) for i, s in enumerate(S.SAFRAS, 1)}},
    }


def _bloco_cox(df: pd.DataFrame) -> tuple[dict, dict]:
    cph_i, d_i = X.ajustar_ingenuo(df)
    covs_i = [c for c in d_i.columns if c not in ("duracao", "evento")]
    ph_i = X.teste_ph(d_i, covs_i, cph_i.params_[covs_i].to_numpy(), stop="duracao", evento="evento")
    c_i = X.concordancia_td(d_i, covs_i, cph_i.params_[covs_i].to_numpy(), stop="duracao", evento="evento")
    tab_i = X.tabela_hr(cph_i)

    ep = X.episodios(df)
    cph_c, d_c = X.ajustar_corrigido(ep)
    covs_c = X.COVS_CORRIGIDO
    ph_c = X.teste_ph(d_c, covs_c, cph_c.params_[covs_c].to_numpy(), stop="stop", evento="evento",
                      start="start", strata="plano")
    c_c = X.concordancia_td(d_c, covs_c, cph_c.params_[covs_c].to_numpy(), stop="stop", evento="evento",
                            start="start", strata="plano")
    tab_c = X.tabela_hr(cph_c)
    cph_p, _ = X.ajustar_complementar(df, ep)
    tab_p = [r for r in X.tabela_hr(cph_p) if r["nome"].startswith("plano")]

    ph_res_i = X.resumo_ph(ph_i, covs_i)
    ph_res_c = X.resumo_ph(ph_c, covs_c)
    por_i = {r["nome"]: r for r in tab_i}
    por_c = {r["nome"]: r for r in tab_c}
    por_p = {r["nome"]: r for r in tab_p}
    verdade = X.verdade_hr()

    ordem = (["canal_busca_paga", "canal_midia_paga", "canal_social", "canal_indicacao", "canal_email_crm",
              "eng_z", "oferta_copa", "disp_desktop", "disp_tablet", "plano_combo", "plano_estudante",
              "plano_anual", "oferta_bf", "promo_vigente", "promo_penhasco", "promo_pos", "reajuste_exposto"])
    comp = []
    for nome in ordem:
        i, c, p = por_i.get(nome), por_c.get(nome), por_p.get(nome)
        v = verdade.get(nome)
        comp.append({
            "nome": nome, "rotulo": X.ROTULOS[nome], "verdade": v,
            "ingenuo": None if i is None else {k: i[k] for k in ("hr", "lo", "hi", "p", "cobre")},
            "corrigido": None if c is None else {k: c[k] for k in ("hr", "lo", "hi", "p", "cobre")},
            "complementar": None if p is None else {k: p[k] for k in ("hr", "lo", "hi", "p", "cobre")},
        })
    cob_c = [r["cobre"] for r in tab_c if r["cobre"] is not None]
    cob_i = [r["cobre"] for r in tab_i if r["cobre"] is not None]
    bf_local = ph_i["efeito_local"]["oferta_bf"]
    cox = {
        "n_episodios": int(len(ep)), "n_eventos": int(df["evento"].sum()),
        "ingenuo": {"coefs": tab_i, "cindex": c_i, "cindex_lifelines": float(cph_i.concordance_index_),
                    "ph": ph_res_i, "ph_global": ph_i["global_rank"],
                    "n_viola": int(sum(r["viola"] for r in ph_res_i)), "n_covs": len(covs_i),
                    "efeito_local_bf": bf_local, "efeito_local_anual": ph_i["efeito_local"]["plano_anual"],
                    "loglik": float(cph_i.log_likelihood_)},
        "corrigido": {"coefs": tab_c, "cindex_td": c_c, "ph": ph_res_c, "ph_global": ph_c["global_rank"],
                      "n_viola": int(sum(r["viola"] for r in ph_res_c)), "n_covs": len(covs_c),
                      "loglik": float(cph_c.log_likelihood_)},
        "complementar_plano": tab_p,
        "plantado_vs_estimado": comp,
        "cobertura": {"corrigido": float(np.mean(cob_c)), "n_corrigido": len(cob_c),
                      "ingenuo": float(np.mean(cob_i)), "n_ingenuo": len(cob_i)},
        "hr_unico_promo_ingenuo": por_i["oferta_bf"]["hr"],
    }
    brutos = {"ph_i": ph_i, "ph_c": ph_c, "tab_c": tab_c, "tab_i": tab_i, "cph_i": cph_i, "cph_c": cph_c}
    return cox, brutos


def _km_vs_verdade(comp: dict, gt: dict) -> list[dict]:
    linhas = []
    for nome, mapa in (("canal", gt["sobrevivencia_verdade"]["por_canal"]),
                       ("plano", gt["sobrevivencia_verdade"]["por_plano"])):
        for g in comp[nome]["grupos"]:
            for h in (12, 18):
                p = g["horizontes"][f"m{h}"]
                if not p["ok"]:
                    continue
                v = mapa[g["chave"]][f"m{h}"]["todos"]
                linhas.append({"tipo": nome, "chave": g["chave"], "rotulo": g["rotulo"], "h": h,
                               "km": p["valor"], "lo": p["lo"], "hi": p["hi"], "verdade": v,
                               "cobre": bool(p["lo"] <= v <= p["hi"]), "erro_pp": p["valor"] - v})
    return linhas


def montar_resultados(df: pd.DataFrame, lat: S.Latente, n_boot: int = C.N_BOOT,
                      com_riscos_competitivos: bool = True, log=print, contar: bool = True) -> tuple[dict, dict]:
    """Executa A–H e devolve (results, objetos_brutos). Cada etapa registra o tempo."""
    t0 = time.time()
    gt = S.construir_ground_truth(df, lat)

    def marca(nome):
        log(f"  [{time.time() - t0:5.1f}s] {nome}")

    res: dict = {"meta": {"versoes": _versoes(), "n_testes": contar_testes() if contar else None, "projeto": "Sobrevivência de assinantes — Gazeta Meridiano (sintético)"},
                 "premissas": _premissas(n_boot)}
    res["dados"] = H.resumo_dados(df)
    marca("A. desenho")
    res["ingenuo_vs_km"] = H.tabela_safras(df)
    marca("B. ingênuo x KM")
    res["comparacoes"] = H.comparacoes(df)
    res["km_vs_verdade"] = _km_vs_verdade(res["comparacoes"], gt)
    marca("C. log-rank + Holm")
    res["cox"], brutos = _bloco_cox(df)
    marca("D. Cox")
    res["valor"] = V.analise_valor(df, n_boot=n_boot)
    res["decisao_verba"] = V.decisao_verba(res["valor"])
    res["acao_mes3"] = V.acao_mes3(df, brutos["tab_c"])
    marca("E. valor por canal")
    ph_i = res["cox"]["ingenuo"]["ph"]
    bf = next(r for r in ph_i if r["nome"] == "oferta_bf")
    res["armadilhas"] = {
        "censura": P.censura_ignorada(df, gt),
        "riscos_proporcionais": P.ph_violada(df, res["cox"]["hr_unico_promo_ingenuo"], brutos["tab_c"],
                                             bf["p_faixas"], bf["p_rank"]),
        "ranking": P.ranking_m12_bruto(df, gt),
    }
    marca("F. armadilhas")
    if com_riscos_competitivos:
        res["riscos_competitivos"] = G.analise(df, gt, n_boot=max(100, n_boot // 5))
        marca("G. riscos competitivos")
    res["explorador"] = H.explorador(df)
    res["verdade"] = {"sobrevivencia": gt["sobrevivencia_verdade"], "cif_m12": gt["cif_verdade_m12"]}
    marca("explorador")
    return res, {"gt": gt, "cox": brutos, "df": df, "lat": lat}


def adicionar_riscos_competitivos(res: dict, extra: dict, n_boot: int = C.N_BOOT, log=print) -> dict:
    """Seção G (riscos competitivos): separada para poder rodar só depois da trava de testes."""
    res["riscos_competitivos"] = G.analise(extra["df"], extra["gt"], n_boot=max(100, n_boot // 5))
    log("  G. riscos competitivos")
    return res


def executar(n_boot: int = C.N_BOOT, com_riscos_competitivos: bool = True, escrever: bool = True,
             log=print) -> tuple[dict, dict]:
    log("Gerando dados sintéticos (seed %d)…" % C.SEED)
    df, lat = S.simular()
    if escrever:
        S.salvar_dataset(df)
    res, extra = montar_resultados(df, lat, n_boot, com_riscos_competitivos, log)
    if escrever:
        S.salvar_ground_truth(extra["gt"])
        C.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        C.RESULTS_JSON.write_text(serializar(res), encoding="utf-8")
        log(f"  results.json gravado em {C.RESULTS_JSON}")
    return res, extra
