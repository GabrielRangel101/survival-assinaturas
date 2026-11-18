"""F (armadilhas) e G (riscos competitivos)."""

from __future__ import annotations

import numpy as np
import pytest

from sobrevivencia import competing as G
from sobrevivencia import config as C
from sobrevivencia import cox as X
from sobrevivencia import pitfalls as P


# ---------------------------------- F ----------------------------------------------

def test_censura_ignorada_km_e_o_mais_proximo_da_verdade(df, gt):
    r = P.censura_ignorada(df, gt)
    erro = {m["id"]: abs(m["erro_pp"]) for m in r["metodos"]}
    assert erro["kaplan_meier"] < 0.02
    assert erro["censura_como_cancelamento"] > 0.25
    assert erro["descartar_censurados"] > 0.04
    km = next(m for m in r["metodos"] if m["id"] == "kaplan_meier")
    assert km["lo"] <= r["verdade"] <= km["hi"]


def test_ph_violada_previsao_ingenua_subestima_penhasco(df):
    cph, d = X.ajustar_ingenuo(df)
    covs = [c for c in d.columns if c not in ("duracao", "evento")]
    ph = X.teste_ph(d, covs, cph.params_[covs].to_numpy(), stop="duracao", evento="evento")
    ep = X.episodios(df)
    c2, _ = X.ajustar_corrigido(ep)
    bf = ph["covariaveis"]["oferta_bf"]
    r = P.ph_violada(df, float(np.exp(cph.params_["oferta_bf"])), X.tabela_hr(c2),
                     bf["faixas"]["p"], bf["rank"]["p"])
    assert r["p_faixas_ingenuo"] < 1e-6
    erro_corr = abs(r["q_previsto_corrigido"] - r["q_observado_bf_mes3"])
    erro_ing = abs(r["q_previsto_ingenuo"] - r["q_observado_bf_mes3"])
    assert erro_corr < erro_ing
    assert r["subestimacao_ingenua"] > 0.5


def test_ranking_bruto_com_safra_pequena_erra_com_frequencia(df, gt):
    r = P.ranking_m12_bruto(df, gt, n_sorteios=300)
    assert r["melhor_verdadeiro"] == "indicacao" and r["pior_verdadeiro"] == "midia_paga"
    assert r["p_acerta_melhor"] < 0.9 and r["p_acerta_pior"] < 0.9
    assert r["largura_media_ic"] > 0.15
    again = P.ranking_m12_bruto(df, gt, n_sorteios=300)
    assert again["p_acerta_melhor"] == r["p_acerta_melhor"]


# ---------------------------------- G ----------------------------------------------

def test_aalen_johansen_exemplo_a_mao():
    # tempos: 1(A) 2(B) 3(censura) 4(A), n = 4
    # t=1: n=4, S_antes=1     -> CIF_A = 1/4 ; S=3/4
    # t=2: n=3, S_antes=3/4   -> CIF_B = 3/4 * 1/3 = 1/4 ; S=1/2
    # t=4: n=1, S_antes=1/2   -> CIF_A = 1/4 + 1/2 = 3/4 ; S=0
    aj = G.aalen_johansen([1, 2, 3, 4], ["A", "B", "", "A"], causas=("A", "B"))
    assert G.cif_em(aj, 1.5) == {"A": pytest.approx(0.25), "B": pytest.approx(0.0)}
    assert G.cif_em(aj, 2.5) == {"A": pytest.approx(0.25), "B": pytest.approx(0.25)}
    fim = G.cif_em(aj, 10)
    assert fim["A"] == pytest.approx(0.75) and fim["B"] == pytest.approx(0.25)


def test_cif_somada_a_sobrevivencia_vale_um(df):
    aj = G.aalen_johansen(df["duracao_meses"], df["causa"])
    soma = sum(aj["cif"].values())
    np.testing.assert_allclose(soma + aj["S"], 1.0, atol=1e-9)
    for v in aj["cif"].values():      # CIF é não decrescente
        assert (np.diff(v) >= -1e-12).all()


def test_um_menos_km_superestima_a_incidencia(df):
    aj = G.aalen_johansen(df["duracao_meses"], df["causa"])
    for k in ("voluntario", "involuntario"):
        cif = G.cif_em(aj, 18.0)[k]
        ing = G.um_menos_km_outras_censuradas(df["duracao_meses"], df["causa"], k, 18.0)
        assert ing > cif


def test_cif_recupera_a_incidencia_verdadeira_em_m12(df, gt):
    aj = G.aalen_johansen(df["duracao_meses"], df["causa"])
    est = G.cif_em(aj, 12.0)
    for k in ("voluntario", "involuntario"):
        assert est[k] == pytest.approx(gt["cif_verdade_m12"][k], abs=0.035)


def test_fim_de_contrato_so_existe_no_plano_anual(df):
    assert set(df.loc[df["causa"] == "fim_contrato", "plano"]) == {"anual"}
    assert (df.loc[df["causa"] == "fim_contrato", "duracao_meses"] >= 12).all()


def test_analise_riscos_competitivos_estrutura(df, gt):
    r = G.analise(df, gt, n_boot=30)
    assert set(r["pontos"]["m12"]) >= set(C.CAUSAS)
    p = r["pontos"]["m18"]["fim_contrato"]
    assert p["lo"] <= p["est"] <= p["hi"]
    assert r["por_plano"]["anual"]["cif_m13"]["fim_contrato"] > 0.2
    assert r["por_plano"]["mensal"]["cif_m13"]["fim_contrato"] == 0.0
