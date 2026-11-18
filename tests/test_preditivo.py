"""Validação fora do tempo, score de risco, alvo da ação do mês 3 e desenho do teste A/B."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from sobrevivencia import config as C
from sobrevivencia import preditivo as P
from sobrevivencia import value as V


@pytest.fixture(scope="module")
def fora(df, latente):
    return P.analise_fora_do_tempo(df, latente)


@pytest.fixture(scope="module")
def acao(df):
    tab = [{"nome": "promo_penhasco", "hr": 2.8, "lo": 2.2, "hi": 3.5}, {"nome": "promo_pos", "hr": 1.4, "lo": 1.1, "hi": 1.8}]
    return V.acao_mes3(df, tab), tab


def test_truncar_em_so_enxerga_o_que_se_sabia_em_t0(df):
    t0 = pd.Timestamp(P.T0)
    d = P.truncar_em(df, P.T0)
    assert d["data_inicio"].max() <= t0 and len(d) < len(df)
    pot = ((t0 - d["data_inicio"]).dt.days + 1) / C.DIAS_POR_MES
    assert (d["duracao_meses"] <= pot + 1e-9).all()
    # evento só se o cancelamento aconteceu até T0
    orig = df.loc[d.index]
    deveria = (orig["evento"] == 1) & (orig["data_cancelamento"] <= t0)
    assert (d["evento"] == 1).sum() == pytest.approx(deveria.sum(), abs=5)
    assert (d.loc[d["evento"] == 0, "duracao_meses"] <= pot[d["evento"] == 0] + 1e-9).all()


def test_prob_cancelar_alinhada_com_as_linhas_do_dataset(df):
    """Regressão: com estratos o lifelines devolve as colunas agrupadas por estrato; o risco tem de voltar na ordem das linhas."""
    treino = P.truncar_em(df, P.T0)
    cph = P.ajustar_score(treino)
    teste = df[df["data_inicio"] > pd.Timestamp(P.T0)]
    r = P.prob_cancelar(cph, teste)
    por_plano = pd.Series(r).groupby(teste["plano"].to_numpy()).mean()
    assert por_plano["anual"] < 0.06                       # o anual quase não cancela nos primeiros 6 meses
    assert por_plano["mensal"] > 3 * por_plano["anual"]
    assert ((r > 0) & (r < 1)).all() and len(r) == len(teste)


def test_modelo_fora_do_tempo_discrimina_perto_do_teto(fora):
    ci = fora["cindex"]
    assert ci["teste"] > 0.6
    assert ci["teste"] <= ci["teto_verdadeiro"] + 0.02      # nenhum modelo passa do risco verdadeiro (a menos de ruído)
    assert abs(ci["treino"] - ci["teste"]) < 0.03           # não houve sobreajuste ao período de treino
    assert ci["treino"] > 0.5 and ci["teto_verdadeiro"] < 0.8


def test_calibracao_por_quintil_cresce_e_acompanha_a_previsao(fora):
    cal = fora["calibracao"]
    assert len(cal) == P.N_FAIXAS
    prev = [c["previsto"] for c in cal]
    obs = [c["observado"] for c in cal]
    assert prev == sorted(prev) and obs == sorted(obs)
    assert all(c["lo"] <= c["observado"] <= c["hi"] for c in cal)
    assert abs(np.mean(prev) - np.mean(obs)) < 0.06       # nível geral razoável, mesmo sem conhecer o reajuste


def test_modelo_subestima_cancelamento_pois_nao_conhecia_o_reajuste(fora):
    for a in fora["agregado"]:
        assert a["erro_pp"] > 0 and a["previsto"] > a["observado"]   # prevê MAIS retenção do que o observado


def test_topo_do_score_concentra_cancelamentos(fora):
    c = fora["captura"]
    assert c["lift"] > 1.4 and c["taxa_topo"] > c["taxa_resto"]
    assert c["captura"] > 0.2 + 0.05                       # mais que o acaso (20% da base)


def test_fora_do_tempo_e_deterministico(df, latente, fora):
    assert P.analise_fora_do_tempo(df, latente) == fora


def test_pontuar_devolve_decis_balanceados(df):
    s = P.pontuar(df)
    assert len(s) == len(df) and s["id_assinante"].is_unique
    assert ((s["prob_cancelar_6m"] > 0) & (s["prob_cancelar_6m"] < 1)).all()
    assert sorted(s["decil_risco"].unique()) == list(range(1, 11))
    assert s["decil_risco"].value_counts().max() - s["decil_risco"].value_counts().min() <= 1
    assert s.loc[s["decil_risco"] == 10, "prob_cancelar_6m"].min() >= s.loc[s["decil_risco"] == 1, "prob_cancelar_6m"].max()


def test_alvo_da_acao_excesso_maior_no_terco_de_maior_risco(df, acao):
    a, tab = acao
    r = P.alvo_acao(df, a, tab)
    f = r["faixas"]
    assert [x["faixa"] for x in f] == ["menor risco", "risco médio", "maior risco"]
    assert f[2]["q_observado"] > f[0]["q_observado"] and f[2]["excesso"] > f[0]["excesso"] > 0
    assert f[2]["efetividade_equilibrio"] < f[0]["efetividade_equilibrio"]
    assert r["n_bf_mes3"] == sum(x["n"] for x in f)
    assert r["liquido_tratar_todos"] == pytest.approx(sum(x["n"] * x["liquido_por_tratado"] for x in f))
    assert r["liquido_tratar_todos"] >= r["liquido_tratar_maior_risco"] > 0
    assert r["pct_tratado_maior_risco"] == pytest.approx(1 / 3, abs=0.01)
    for x in f:   # o benefício por tratado é efetividade x excesso x valor do retido
        assert x["beneficio_por_tratado"] == pytest.approx(
            a["projetado"]["efetividade_base"] * x["valor_retido_esperado"])


def test_desenho_do_teste_confere_com_a_formula_de_duas_proporcoes(df, acao):
    a, tab = acao
    alvo = P.alvo_acao(df, a, tab)
    t = P.desenho_teste(a, alvo)
    za, zb = stats.norm.ppf(1 - C.ALPHA / 2), stats.norm.ppf(0.8)
    for l in t["linhas"]:
        p0, p1 = l["p_controle"], l["p_tratamento"]
        pb = (p0 + p1) / 2
        n = ((za * np.sqrt(2 * pb * (1 - pb)) + zb * np.sqrt(p0 * (1 - p0) + p1 * (1 - p1))) ** 2) / (p0 - p1) ** 2
        assert l["n_por_braco"] == pytest.approx(n, rel=0.05)
        assert l["n_total"] == 2 * l["n_por_braco"]
    n_braco = [l["n_por_braco"] for l in t["linhas"]]
    assert n_braco == sorted(n_braco, reverse=True)          # efetividade maior = menos gente
    assert t["vivos_mes3_coorte"] == pytest.approx(a["projetado"]["vivos_mes3"])
    # uma campanha de Black Friday não tem poder para efetividades realistas
    assert t["efetividade_minima_detectavel"] > max(C.ACAO_EFETIVIDADES)
    assert t["linhas"][1]["campanhas_necessarias"] > 2
