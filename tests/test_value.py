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
    ltv_receita = float(np.sum(10.0 * np.exp(-lam * np.arange(24)) * d))
    assert a["ltv_receita"] == pytest.approx(ltv_receita, rel=0.01)
    assert a["ltv"] == pytest.approx(ltv_receita * C.MARGEM_POR_REAL, rel=0.01)   # LTV de contribuição
    assert a["ltv_proj"] / a["ltv"] < 0.02


def test_projecao_da_cauda_recupera_a_verdade_quando_o_suporte_acaba_cedo():
    lam = 0.05
    dur, ev = _exponencial(lam=lam, corte=12.0)        # só observamos até 12 meses
    P = np.full((len(dur), 24), 10.0)
    a = V.avaliar(dur, ev, P, cac=1.0)
    assert a["t_sup"] <= 12.0 and a["ltv_proj"] > 0 and a["rmst_proj"] > 0
    ltv_teorico = float(np.sum(10.0 * np.exp(-lam * np.arange(24)) * V.fator_desconto(24))) * C.MARGEM_POR_REAL
    assert a["ltv"] == pytest.approx(ltv_teorico, rel=0.03)   # extrapolação razoável
    assert a["ltv_medido"] + a["ltv_proj"] == pytest.approx(a["ltv"])


def test_payback_exemplo_a_mao():
    # ninguém cancela; preço 30 com margem por real de 0,665 = 19,95 por mês (descontado): mês 0 acumula ~20,
    # mês 1 ~40, mês 2 ~59 (>= 50) -> payback = 3 mensalidades (a margem alonga o payback de 2 para 3)
    dur = np.full(200, 24.0)
    ev = np.zeros(200, dtype=int)
    P = np.full((200, 24), 30.0)
    assert V.avaliar(dur, ev, P, cac=50.0)["payback"] == 3.0
    assert V.avaliar(dur, ev, P, cac=1e9)["payback"] == C.HORIZONTE_LTV + 1.0


def test_preco_por_idade_aplica_promocao_black_friday(df):
    P = V.preco_por_idade(df)
    bf = (df["oferta_entrada"] == "black_friday").to_numpy()
    base = df["plano"].map({p: V.preco_vigente(p) for p in C.PLANOS}).to_numpy()   # preço de tabela VIGENTE
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
    r, m = d["realocacao"]["pior_para_melhor"], d["realocacao"]["midia_para_melhor"]
    assert r["origem"] == "busca_paga" and r["destino"] == "indicacao" and m["origem"] == "midia_paga"
    assert r["linhas"][0]["ganho"] > m["linhas"][0]["ganho"] > 0
    for l in d["linhas"]:
        assert l["valor_liquido"] == pytest.approx(l["ltv_total"] - C.VERBA_EXEMPLO)


def test_ltv_e_de_contribuicao_receita_vezes_margem(valor):
    for c in valor["canais"]:
        assert c["ltv"]["est"] == pytest.approx(c["ltv_receita"]["est"] * C.MARGEM_POR_REAL, rel=1e-9)
    assert C.MARGEM_POR_REAL == pytest.approx(C.MARGEM_CONTRIBUICAO - C.CUSTO_COBRANCA)


def test_incerteza_do_cac_alarga_o_intervalo_e_reduz_a_certeza_do_ranking(valor):
    por = {c["canal"]: c for c in valor["canais"]}
    for c in valor["canais"]:
        assert c["ltv_cac_incerteza"]["lo"] <= c["ltv_cac"]["est"] <= c["ltv_cac_incerteza"]["hi"]
        assert (c["ltv_cac_incerteza"]["hi"] - c["ltv_cac_incerteza"]["lo"]
                > c["ltv_cac"]["hi"] - c["ltv_cac"]["lo"])
    esc = [c for c in valor["canais"] if c["escalavel"]]
    assert sum(c["prob_melhor_ltv_cac_cac_fixo"] for c in esc) == pytest.approx(1.0)
    # com CAC fixo a líder é quase sempre a mesma; com CAC incerto a vantagem deixa de ser certa
    assert por["indicacao"]["prob_melhor_ltv_cac_cac_fixo"] > por["indicacao"]["prob_melhor_ltv_cac"]
    assert por["indicacao"]["prob_melhor_ltv_cac"] < 1.0


def test_ranking_por_permanencia_nao_usa_o_cac(valor):
    por = {c["canal"]: c for c in valor["canais"]}
    esc = [c for c in valor["canais"] if c["escalavel"]]
    assert valor["ranking_ltv"] == [c["canal"] for c in sorted(esc, key=lambda c: -c["ltv"]["est"])]
    assert valor["ranking_ltv"][0] == "indicacao" and valor["ranking_ltv"][-1] == "midia_paga"
    assert por["midia_paga"]["cac"] < por["busca_paga"]["cac"]   # o mais barato é o de pior permanência


def test_sensibilidade_cac_empate_e_ponto_de_virada(valor):
    s = valor["sensibilidade_cac"]
    por = {c["canal"]: c for c in valor["canais"]}
    melhor = por[s["melhor"]]
    for c, e in s["empate"].items():
        # com o CAC de empate, o retorno por real do canal iguala o do melhor
        assert por[c]["ltv"]["est"] / e["cac_empate"] == pytest.approx(melhor["ltv_cac"]["est"])
        assert e["variacao"] < 0                                  # para empatar, o CAC dele teria de cair
        assert e["queda"] == pytest.approx(-e["variacao"]) and e["queda"] > 0
    assert melhor["ltv"]["est"] / s["cac_melhor_perde_lideranca"] == pytest.approx(
        por[s["segundo"]]["ltv_cac"]["est"])
    assert s["alta_cac_melhor_perde"] > 0


def test_realocacao_cai_com_o_cac_marginal_e_tem_ponto_de_equilibrio(valor):
    r = valor["realocacao"]["pior_para_melhor"]
    ganhos = [l["ganho"] for l in r["linhas"]]
    assert ganhos == sorted(ganhos, reverse=True) and ganhos[0] > 0
    por = {c["canal"]: c for c in valor["canais"]}
    rd, ro = por[r["destino"]]["ltv_cac"]["est"], por[r["origem"]]["ltv_cac"]["est"]
    assert r["premio_equilibrio"] == pytest.approx(rd / ro - 1.0)
    assert C.VERBA_EXEMPLO * (rd / (1 + r["premio_equilibrio"]) - ro) == pytest.approx(0.0, abs=1e-6)
    for l in r["linhas"]:
        assert l["lo"] <= l["ganho"] <= l["hi"] and 0.0 <= l["prob_positivo"] <= 1.0


def test_canais_proprios_ficam_fora_da_realocacao(valor):
    r = valor["realocacao"]
    for k in r.values():
        assert k["origem"] in C.CANAIS_ESCALAVEIS and k["destino"] in C.CANAIS_ESCALAVEIS
    assert not any(c["escalavel"] for c in valor["canais"] if c["canal"] in ("organico", "email_crm"))


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
