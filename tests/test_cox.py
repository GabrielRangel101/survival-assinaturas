"""Cox: recuperação dos efeitos plantados, detecção da violação de PH e correção."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from lifelines import CoxPHFitter
from lifelines.statistics import proportional_hazard_test

from sobrevivencia import config as C
from sobrevivencia import cox as X


@pytest.fixture(scope="module")
def ingenuo(df):
    cph, d = X.ajustar_ingenuo(df)
    covs = [c for c in d.columns if c not in ("duracao", "evento")]
    ph = X.teste_ph(d, covs, cph.params_[covs].to_numpy(), stop="duracao", evento="evento")
    return cph, d, covs, ph


@pytest.fixture(scope="module")
def ep(df):
    return X.episodios(df)


@pytest.fixture(scope="module")
def corrigido(ep):
    cph, d = X.ajustar_corrigido(ep)
    covs = X.COVS_CORRIGIDO
    ph = X.teste_ph(d, covs, cph.params_[covs].to_numpy(), stop="stop", evento="evento",
                    start="start", strata="plano")
    return cph, d, covs, ph


# ------------------------------------------------------------------------------------
# Episódios
# ------------------------------------------------------------------------------------

def test_episodios_preservam_tempo_e_eventos(df, ep):
    soma = ep.groupby("i").apply(lambda g: (g["stop"] - g["start"]).sum(), include_groups=False)
    np.testing.assert_allclose(soma.to_numpy(), df["duracao_meses"].to_numpy(), atol=1e-9)
    assert ep["evento"].sum() == df["evento"].sum()
    assert (ep["stop"] > ep["start"]).all()
    # episódios de um assinante são contíguos
    ordenado = ep.sort_values(["i", "start"])
    prox = ordenado.groupby("i")["start"].shift(-1)
    fim = ordenado["stop"]
    m = prox.notna()
    np.testing.assert_allclose(prox[m].to_numpy(), fim[m].to_numpy(), atol=1e-12)


def test_divisao_em_episodios_nao_altera_a_verossimilhanca(df, ep):
    """Propriedade do Cox: dividir o tempo (covariáveis constantes) não muda as estimativas."""
    ing, d = X.ajustar_ingenuo(df)
    cols = ["canal_midia_paga", "canal_indicacao", "eng_z", "oferta_copa"]
    um = d[cols + ["duracao", "evento"]]
    c1 = CoxPHFitter().fit(um, "duracao", "evento")
    ev = ep[cols + ["start", "stop", "evento"]]
    c2 = CoxPHFitter().fit(ev, "stop", "evento", entry_col="start")
    np.testing.assert_allclose(c1.params_[cols].to_numpy(), c2.params_[cols].to_numpy(), atol=2e-3)


# ------------------------------------------------------------------------------------
# Recuperação dos efeitos plantados (modelo corrigido)
# ------------------------------------------------------------------------------------

EFEITOS_CHAVE = ["canal_midia_paga", "canal_indicacao", "eng_z", "oferta_copa",
                 "promo_penhasco", "reajuste_exposto"]


@pytest.mark.parametrize("nome", EFEITOS_CHAVE)
def test_hr_plantado_dentro_da_tolerancia_e_ic_cobre(corrigido, nome):
    tab = {r["nome"]: r for r in X.tabela_hr(corrigido[0])}
    r = tab[nome]
    assert r["verdade"] is not None
    assert abs(r["hr"] / r["verdade"] - 1) < 0.20, (nome, r["hr"], r["verdade"])
    assert r["lo"] <= r["verdade"] <= r["hi"], (nome, r["lo"], r["hi"], r["verdade"])


def test_direcao_dos_efeitos_plantados(corrigido):
    tab = {r["nome"]: r for r in X.tabela_hr(corrigido[0])}
    assert tab["canal_midia_paga"]["lo"] > 1       # mídia paga pior que orgânico
    assert tab["canal_indicacao"]["hi"] < 1        # indicação melhor
    assert tab["eng_z"]["hi"] < 1                  # engajamento protetor
    assert tab["oferta_copa"]["lo"] > 1            # Passe Copa pior
    assert tab["promo_penhasco"]["lo"] > 2         # penhasco forte
    assert tab["promo_vigente"]["hr"] < tab["promo_pos"]["hr"] < tab["promo_penhasco"]["hr"]


def test_cobertura_geral_dos_ic_do_modelo_corrigido(corrigido):
    tab = [r for r in X.tabela_hr(corrigido[0]) if r["verdade"] is not None]
    cobre = np.mean([r["cobre"] for r in tab])
    assert cobre >= 0.85  # esperado ~95%; tolerância para uma única realização


def test_efeito_nulo_de_dispositivo_nao_e_detectado(corrigido):
    tab = {r["nome"]: r for r in X.tabela_hr(corrigido[0])}
    for nome in ("disp_desktop", "disp_tablet"):
        assert tab[nome]["lo"] <= 1.0 <= tab[nome]["hi"]


def test_modelo_complementar_recupera_hr_de_plano(df, ep):
    cph, _ = X.ajustar_complementar(df, ep)
    tab = {r["nome"]: r for r in X.tabela_hr(cph)}
    for nome in ("plano_combo", "plano_estudante"):
        assert tab[nome]["lo"] <= tab[nome]["verdade"] <= tab[nome]["hi"]


# ------------------------------------------------------------------------------------
# Violação de riscos proporcionais: detectar e corrigir
# ------------------------------------------------------------------------------------

def test_ph_violacao_do_plano_anual_detectada(ingenuo):
    ph = ingenuo[3]["covariaveis"]["plano_anual"]
    assert ph["rank"]["p"] < 1e-10 and ph["faixas"]["p"] < 1e-10


def test_ph_violacao_da_promocao_detectada_por_faixas_de_idade(ingenuo):
    ph = ingenuo[3]["covariaveis"]["oferta_bf"]
    assert ph["faixas"]["p"] < 1e-6          # o penhasco aparece por faixa de idade
    # o efeito local no mês 3–4 é muito maior que antes/depois
    loc = {(x["ini"], x["fim"]): x["hr_local"] for x in ingenuo[3]["efeito_local"]["oferta_bf"]}
    assert loc[(3.0, 4.0)] > 2.0 and loc[(0.0, 3.0)] < 1.3 and loc[(6.0, 12.0)] < 1.5


def test_ph_global_ingenuo_rejeita(ingenuo):
    assert ingenuo[3]["global_rank"]["p"] < 1e-10


def test_ph_modelo_corrigido_nao_rejeita(corrigido):
    assert corrigido[3]["global_rank"]["p"] > 0.05
    for nome, r in corrigido[3]["covariaveis"].items():
        assert r["rank"]["p"] > 0.01, nome


def test_ph_conclusao_concorda_com_lifelines(ingenuo):
    cph, d, covs, ph = ingenuo
    ref = proportional_hazard_test(cph, d, time_transform="rank").summary
    assert ref.loc["plano_anual", "p"] < 1e-10 and ph["covariaveis"]["plano_anual"]["rank"]["p"] < 1e-10
    for nome in ("eng_z", "canal_midia_paga", "disp_desktop"):
        assert ref.loc[nome, "p"] > 0.05 and ph["covariaveis"][nome]["rank"]["p"] > 0.05
    # ordem de grandeza da estatística do plano anual é a mesma
    ours = ph["covariaveis"]["plano_anual"]["rank"]["chi2"]
    assert 0.5 < ours / ref.loc["plano_anual", "test_statistic"] < 2.0


def test_ph_sem_violacao_em_dados_com_risco_proporcional():
    """Erro tipo I: exponenciais com HR constante não devem ser rejeitadas."""
    rng = np.random.default_rng(7)
    n = 6000
    x = rng.integers(0, 2, n).astype(float)
    t = rng.exponential(1 / (0.05 * np.exp(0.5 * x)))
    c = rng.uniform(0, 40, n)
    d = pd.DataFrame({"x": x, "duracao": np.minimum(t, c), "evento": (t <= c).astype(int)})
    cph = CoxPHFitter().fit(d, "duracao", "evento")
    ph = X.teste_ph(d, ["x"], cph.params_.to_numpy(), stop="duracao", evento="evento")
    assert ph["covariaveis"]["x"]["rank"]["p"] > 0.01
    assert ph["covariaveis"]["x"]["faixas"]["p"] > 0.01


def test_promocao_ingenua_subestima_o_penhasco(ingenuo, corrigido):
    hr_unico = float(np.exp(ingenuo[0].params_["oferta_bf"]))
    tab = {r["nome"]: r for r in X.tabela_hr(corrigido[0])}
    assert hr_unico < 0.6 * tab["promo_penhasco"]["hr"]


# ------------------------------------------------------------------------------------
# C-index
# ------------------------------------------------------------------------------------

def test_cindex_td_confere_com_lifelines(ingenuo):
    cph, d, covs, _ = ingenuo
    c = X.concordancia_td(d, covs, cph.params_[covs].to_numpy(), stop="duracao", evento="evento")
    assert c == pytest.approx(cph.concordance_index_, abs=1e-9)


def test_cindex_corrigido_entre_zero_e_um(corrigido):
    cph, d, covs, _ = corrigido
    c = X.concordancia_td(d, covs, cph.params_[covs].to_numpy(), stop="stop", evento="evento",
                          start="start", strata="plano")
    assert 0.55 < c < 0.9
