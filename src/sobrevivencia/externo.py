"""Validação externa: o mesmo pipeline (Kaplan-Meier, log-rank com Holm, Cox, Schoenfeld e correção) num
dataset PÚBLICO de churn cujo processo gerador não fui eu quem plantou.

Dataset: amostra pública de churn de uma operadora de telecom publicada pela IBM (Apache-2.0), versionada
em ``data_externo/`` com o SHA-256 conferido. Não é dado de operação real e não é de assinatura de jornal;
serve para mostrar o que o método encontra quando NÃO conheço a resposta de antemão.

Convenção (a usual com este arquivo): ``tenure`` é a duração em meses e ``Churn = Yes`` é o evento; quem não
cancelou é censurado em ``tenure``. A documentação do arquivo diz que o cancelamento é "no último mês", o que
sugere uma amostra de estoque; por isso uma leitura alternativa (tábua de período, com entrada tardia) é
calculada ao lado, e a diferença entre as duas é reportada.
"""

from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd
from lifelines import CoxPHFitter, KaplanMeierFitter

from . import config as C
from . import cox as X
from . import km as K

ARQUIVO = C.RAIZ / "data_externo" / "telco_churn_ibm.csv"
SHA256 = "16320c9c1ec72448db59aa0a26a0b95401046bef5d02fd3aeb906448e3055e91"
HORIZONTES = (6, 12, 24, 36, 48, 60)
CONTRATOS = ("Month-to-month", "One year", "Two year")
ROT_CONTRATO = {"Month-to-month": "Mensal (sem fidelidade)", "One year": "Contrato de 1 ano", "Two year": "Contrato de 2 anos"}

ROT_COV = {
    "contrato_1ano": "Contrato de 1 ano (vs mensal)",
    "contrato_2anos": "Contrato de 2 anos (vs mensal)",
    "internet_fibra": "Internet: fibra óptica (vs DSL)",
    "internet_nenhuma": "Sem internet (vs DSL)",
    "cheque_eletronico": "Pagamento por cheque eletrônico",
    "fatura_digital": "Fatura digital",
    "idoso": "Cliente idoso",
    "parceiro": "Tem parceiro(a)",
    "dependentes": "Tem dependentes",
    "suporte_tecnico": "Contratou suporte técnico",
    "cobranca_z": "Cobrança mensal (+1 desvio-padrão)",
}


def conferir_arquivo() -> bool:
    return hashlib.sha256(ARQUIVO.read_bytes()).hexdigest() == SHA256


def carregar() -> pd.DataFrame:
    if not conferir_arquivo():
        raise ValueError("data_externo/telco_churn_ibm.csv não confere com o SHA-256 esperado")
    d = pd.read_csv(ARQUIVO)
    d = d[d["tenure"] > 0].copy()  # 11 clientes com tenure 0 (ainda sem cobrança) ficam de fora
    d["duracao"] = d["tenure"].astype(float)
    d["evento"] = (d["Churn"] == "Yes").astype(int)
    return d.reset_index(drop=True)


def _covs(d: pd.DataFrame) -> pd.DataFrame:
    X_ = pd.DataFrame(index=d.index)
    X_["contrato_1ano"] = (d["Contract"] == "One year").astype(float)
    X_["contrato_2anos"] = (d["Contract"] == "Two year").astype(float)
    X_["internet_fibra"] = (d["InternetService"] == "Fiber optic").astype(float)
    X_["internet_nenhuma"] = (d["InternetService"] == "No").astype(float)
    X_["cheque_eletronico"] = (d["PaymentMethod"] == "Electronic check").astype(float)
    X_["fatura_digital"] = (d["PaperlessBilling"] == "Yes").astype(float)
    X_["idoso"] = d["SeniorCitizen"].astype(float)
    X_["parceiro"] = (d["Partner"] == "Yes").astype(float)
    X_["dependentes"] = (d["Dependents"] == "Yes").astype(float)
    X_["suporte_tecnico"] = (d["TechSupport"] == "Yes").astype(float)
    X_["cobranca_z"] = (d["MonthlyCharges"] - d["MonthlyCharges"].mean()) / d["MonthlyCharges"].std()
    return X_


def _pontos(dur, ev, horizontes=HORIZONTES) -> dict:
    out = {}
    for h in horizontes:
        p = K.km_ponto(dur, ev, h)
        out[f"m{h}"] = {"valor": p["valor"] if p["estimavel"] else None,
                        "lo": p["lo"] if p["estimavel"] else None, "hi": p["hi"] if p["estimavel"] else None,
                        "n_risco": int(p["n_risco"]), "ok": bool(p["estimavel"])}
    return out


def _tab(cph: CoxPHFitter) -> list[dict]:
    s = cph.summary
    return [{"nome": n, "rotulo": ROT_COV.get(n, n), "hr": float(np.exp(r["coef"])),
             "lo": float(np.exp(r["coef lower 95%"])), "hi": float(np.exp(r["coef upper 95%"])), "p": float(r["p"])}
            for n, r in s.iterrows()]


def analise(d: pd.DataFrame | None = None) -> dict:
    d = carregar() if d is None else d
    dur, ev = d["duracao"], d["evento"]
    n_arquivo = int(len(pd.read_csv(ARQUIVO)))
    out: dict = {
        "fonte": {"nome": "Amostra pública de churn de telecom (IBM, Apache-2.0)", "sha256": SHA256,
                  "n_linhas_arquivo": n_arquivo, "n": int(len(d)), "excluidos_tenure_zero": n_arquivo - int(len(d))},
        "dados": {"n": int(len(d)), "n_eventos": int(ev.sum()), "pct_eventos": float(ev.mean()),
                  "duracao_max": float(dur.max()), "por_contrato": {c: int((d["Contract"] == c).sum()) for c in CONTRATOS}},
    }
    out["km_global"] = _pontos(dur, ev)
    # primeiro mês: risco do 1º mês entre todos os clientes expostos e peso no total de cancelamentos
    c1 = int(((d["duracao"] == 1.0) & (d["evento"] == 1)).sum())
    mm = d["Contract"] == "Month-to-month"
    c1_mm = int(((d["duracao"] == 1.0) & (d["evento"] == 1) & mm).sum())
    out["primeiro_mes"] = {"n_expostos": int(len(d)), "n_cancelaram": c1, "taxa": float(c1 / len(d)),
                           "taxa_contrato_mensal": float(c1_mm / mm.sum()),
                           "pct_de_todos_cancelamentos": float(c1 / ev.sum())}
    # por contrato
    grupos = []
    for c in CONTRATOS:
        s = d[d["Contract"] == c]
        km = K.km_curve(s["duracao"], s["evento"])
        grupos.append({"chave": c, "rotulo": ROT_CONTRATO[c], "n": int(len(s)), "eventos": int(s["evento"].sum()),
                       "pct_eventos": float(s["evento"].mean()), "horizontes": _pontos(s["duracao"], s["evento"]),
                       "mediana": float(km.t[km.S <= 0.5][0]) if (km.S <= 0.5).any() else None})
    lr = K.logrank(dur, ev, d["Contract"])
    pares = K.logrank_pares_holm(dur, ev, d["Contract"])
    for x in pares:
        x["rotulo_a"], x["rotulo_b"] = ROT_CONTRATO[x["a"]], ROT_CONTRATO[x["b"]]
    out["contrato"] = {"grupos": grupos, "logrank": {"chi2": lr["chi2"], "df": lr["df"], "p": lr["p"]}, "pares": pares}
    # leitura alternativa: tábua de período (entrada tardia em tenure-1)
    kp = KaplanMeierFitter().fit(d["duracao"], d["evento"], entry=d["duracao"] - 1.0)
    out["leitura_periodo"] = {f"m{h}": float(kp.predict(h)) for h in (3, 6, 12)}

    # Cox ingênuo (riscos proporcionais, uma linha de base) e diagnóstico
    Xc = _covs(d)
    di = pd.concat([Xc, dur.rename("duracao"), ev.rename("evento")], axis=1)
    cph_i = CoxPHFitter().fit(di, "duracao", "evento")
    covs = list(Xc.columns)
    ph_i = X.teste_ph(di, covs, cph_i.params_[covs].to_numpy(), stop="duracao", evento="evento")
    res_i = X.resumo_ph(ph_i, covs)
    for r in res_i:
        r["rotulo"] = ROT_COV[r["nome"]]
    # Cox corrigido: estratificado por contrato (cada contrato com seu risco de base)
    covs_c = [c for c in covs if not c.startswith("contrato_")]
    dc = pd.concat([Xc[covs_c], dur.rename("duracao"), ev.rename("evento"), d["Contract"].rename("contrato")], axis=1)
    cph_c = CoxPHFitter().fit(dc, "duracao", "evento", strata=["contrato"])
    ph_c = X.teste_ph(dc, covs_c, cph_c.params_[covs_c].to_numpy(), stop="duracao", evento="evento", strata="contrato")
    res_c = X.resumo_ph(ph_c, covs_c)
    for r in res_c:
        r["rotulo"] = ROT_COV[r["nome"]]
    out["cox"] = {
        "ingenuo": {"coefs": _tab(cph_i), "ph": res_i, "ph_global": ph_i["global_rank"],
                    "n_viola": int(sum(r["viola"] for r in res_i)), "n_covs": len(covs),
                    "cindex": float(cph_i.concordance_index_),
                    "efeito_local": {k: ph_i["efeito_local"][k] for k in ("contrato_1ano", "contrato_2anos")}},
        "corrigido": {"coefs": _tab(cph_c), "ph": res_c, "ph_global": ph_c["global_rank"],
                      "n_viola": int(sum(r["viola"] for r in res_c)), "n_covs": len(covs_c),
                      "cindex": float(cph_c.concordance_index_)},
    }
    # onde está o risco: taxa mensal de cancelamento por faixa de tenure (eventos / meses expostos), por contrato
    faixas = [(0, 1), (1, 3), (3, 6), (6, 12), (12, 24), (24, 48), (48, 73)]
    linhas = []
    for a, b in faixas:
        exp_ = np.clip(np.minimum(d["duracao"], b) - a, 0, None)
        ev_f = (d["evento"] == 1) & (d["duracao"] > a) & (d["duracao"] <= b)
        row = {"ini": a, "fim": b, "eventos": int(ev_f.sum()), "taxa_mensal": float(ev_f.sum() / exp_.sum())}
        for c in CONTRATOS:
            m = d["Contract"] == c
            e_c = np.clip(np.minimum(d.loc[m, "duracao"], b) - a, 0, None).sum()
            row[c] = float(ev_f[m].sum() / e_c) if e_c > 0 else None
        linhas.append(row)
    out["taxa_por_faixa"] = linhas
    return out
