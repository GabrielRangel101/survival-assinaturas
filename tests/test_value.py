"""RMST, LTV descontado, payback, bootstrap e decisão em R$."""

from __future__ import annotations

import numpy as np
import pytest

from sobrevivencia import config as C
from sobrevivencia import cox as X
from sobrevivencia import value as V


def _exponencial(n=20000, lam=0.05, corte=None, seed=3):
    rng = np.random.default_rng(seed)
    t = rng.exponential(1 / lam, n)
    c = np.full(n, 1e9 if corte is None else corte)
    return np.minimum(t, c), (t <= c).astype(int)


def test_rmst_e_ltv_exponencial_batem_com_a_formula_fechada():
    lam = 0.05
    dur, ev = _exponencial(lam=lam)
    P = np.full((len(dur), 24), 10.0)
    a = V.avaliar(dur, ev, P, cac=1.0)
    rmst_teorico = (1 - np.exp(-lam * 24)) / lam
    assert a["rmst"] == pytest.approx(rmst_teorico, rel=0.01)
    d = V.fator_desconto(24)
    ltv_teorico = float(np.sum(10.0 * np.exp(-lam * np.arange(24)) * d))
    assert a["ltv"] == pytest.approx(ltv_teorico, rel=0.01)
    assert a["ltv_proj"] / a["ltv"] < 0.02


def test_projecao_da_cauda_recupera_a_verdade_quando_o_suporte_acaba_cedo():
    lam = 0.05
    dur, ev = _exponencial(lam=lam, corte=12.0)        # só observamos até 12 meses
    P = np.full((len(dur), 24), 10.0)
    a = V.avaliar(dur, ev, P, cac=1.0)
    assert a["t_sup"] <= 12.0 and a["ltv_proj"] > 0 and a["rmst_proj"] > 0
    ltv_teorico = float(np.sum(10.0 * np.exp(-lam * np.arange(24)) * V.fator_desconto(24)))
    assert a["ltv"] == pytest.approx(ltv_teorico, rel=0.03)   # extrapolação razoável
    assert a["ltv_medido"] + a["ltv_proj"] == pytest.approx(a["ltv"])


def test_payback_exemplo_a_mao():
    # ninguém cancela; preço 30, CAC 50: mês 0 acumula 30 (<50); mês 1 acumula 30 + 30*d (~59,7 >= 50)
    # -> payback = 2 mensalidades
    dur = np.full(200, 24.0)
    ev = np.zeros(200, dtype=int)
    P = np.full((200, 24), 30.0)
    assert V.avaliar(dur, ev, P, cac=50.0)["payback"] == 2.0
    assert V.avaliar(dur, ev, P, cac=1e9)["payback"] == C.HORIZONTE_LTV + 1.0


def test_preco_por_idade_aplica_promocao_black_friday(df):
    P = V.preco_por_idade(df)
    bf = (df["oferta_entrada"] == "black_friday").to_numpy()
    base = df["plano"].map(C.PRECO).to_numpy()
    np.testing.assert_allclose(P[bf, 0], base[bf] * (1 - C.PROMO_DESCONTO))
    np.testing.assert_allclose(P[bf, C.PROMO_MESES], base[bf])
    np.testing.assert_allclose(P[~bf, 0], base[~bf])


@pytest.fixture(scope="module")
def valor(df):
    return V.analise_valor(df, n_boot=C.N_BOOT_RAPIDO)


def test_bootstrap_deterministico_e_ic_contem_estimativa(df, valor):
    again = V.analise_valor(df, n_boot=C.N_BOOT_RAPIDO)
    assert again["canais"][0]["ltv"] == valor["canais"][0]["ltv"]
    for c in valor["canais"]:
        for k in ("rmst", "ltv", "ltv_cac"):
            assert c[k]["lo"] <= c[k]["est"] <= c[k]["hi"]
        assert c["ltv_medido"]["est"] + c["ltv_proj"]["est"] == pytest.approx(c["ltv"]["est"])
        assert 0 < c["pct_ltv_medido"] <= 1


def test_ltv_ordem_reflete_retencao_plantada(valor):
    por = {c["canal"]: c for c in valor["canais"]}
    assert por["indicacao"]["rmst"]["est"] > por["organico"]["rmst"]["est"] > por["midia_paga"]["rmst"]["est"]
    assert por["midia_paga"]["ltv"]["est"] < por["organico"]["ltv"]["est"]


def test_cac_sozinho_engana_e_ltv_cac_inverte_o_ranking(valor):
    assert valor["rank_inverte"]
    assert valor["ranking_cac"][0] == "midia_paga"            # mais barato entre os pagos
    assert valor["ranking_ltv_cac"][0] == "indicacao"          # melhor quando se conta permanência
    assert valor["ranking_ltv_cac"][-1] == "busca_paga"


def test_probabilidades_de_melhor_canal_somam_um(valor):
    p = [c["prob_melhor_ltv_cac"] for c in valor["canais"] if c["escalavel"]]
    assert sum(p) == pytest.approx(1.0)


def test_decisao_de_verba_consistente(valor):
    d = V.decisao_verba(valor)
    assert d["melhor"] == "indicacao" and d["pior"] == "busca_paga" and d["mais_barato"] == "midia_paga"
    assert d["ganho_realocar_pior_para_melhor"] > d["ganho_realocar_midia_paga_para_melhor"] > 0
    for l in d["linhas"]:
        assert l["valor_liquido"] == pytest.approx(l["ltv_total"] - C.VERBA_EXEMPLO)


def test_acao_mes3_separa_medido_de_projetado(df):
    ep = X.episodios(df)
    cph, _ = X.ajustar_corrigido(ep)
    a = V.acao_mes3(df, X.tabela_hr(cph))
    m, p = a["medido"], a["projetado"]
    pen = m["periodos"]["promo_penhasco"]
    assert m["q_penhasco"] > 0.07 and pen["excesso"] > 0.03
    assert pen["excesso_lo"] < pen["excesso"] < pen["excesso_hi"]
    assert p["cancelamentos_em_excesso_penhasco"] > 0 and p["valor_assinante_retido"] > 0
    ef = p["efetividade_equilibrio"]
    assert 0 < ef < 1
    # no ponto de equilíbrio o líquido é zero
    assert ef * p["valor_perdido_penhasco"] - p["custo_acao"] == pytest.approx(0.0, abs=1e-6)
    assert [c["efetividade"] for c in p["cenarios"]] == list(C.ACAO_EFETIVIDADES)
