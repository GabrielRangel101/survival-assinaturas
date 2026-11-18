"""Camada de operação: ponte de MRR, NRR/GRR, reativação, troca de plano e funil de trial."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from sobrevivencia import config as C
from sobrevivencia import operacao as O


@pytest.fixture(scope="module")
def ev(df):
    return O.gerar_eventos(df)


@pytest.fixture(scope="module")
def M(ev):
    return O.matrizes(ev)


@pytest.fixture(scope="module")
def ponte(M):
    return O.ponte_mrr(M)


def test_gerar_eventos_nao_altera_os_tempos_de_vida(df, ev):
    for col in df.columns:
        pd.testing.assert_series_equal(df[col], ev[col], check_names=True)


def test_gerar_eventos_e_deterministico(df, ev):
    again = O.gerar_eventos(df)
    pd.testing.assert_frame_equal(ev, again)


def test_reativacao_so_de_quem_cancelou_e_antes_do_corte(ev):
    r = ev[ev["reativou"] == 1]
    assert len(r) > 0 and (r["evento"] == 1).all()
    assert (r["data_reativacao"] > r["data_cancelamento"]).all()
    assert (r["data_reativacao"] <= pd.Timestamp(C.CORTE)).all()
    # o segundo cancelamento, quando existe, vem depois da reativação e antes do corte
    c2 = r.dropna(subset=["data_cancelamento2"])
    assert (c2["data_cancelamento2"] > c2["data_reativacao"]).all() and (c2["data_cancelamento2"] <= pd.Timestamp(C.CORTE)).all()
    assert (ev.loc[ev["reativou"] == 0, "data_reativacao"].isna()).all()


def test_taxa_de_reativacao_por_causa_perto_da_premissa(ev):
    canc = ev[(ev["evento"] == 1) & (ev["data_cancelamento"] <= pd.Timestamp(C.CORTE) - pd.Timedelta(days=365))]
    for causa, p in C.REATIVA_PROB.items():
        s = canc[canc["causa"] == causa]
        if len(s) > 200:
            assert abs(s["reativou"].mean() - p) < 0.05, causa


def test_troca_de_plano_valida(ev):
    t = ev[ev["plano_troca"] != ""]
    assert len(t) > 0
    assert (t["plano"] != t["plano_troca"]).all() and not (t["plano"] == "anual").any()
    fim = np.where(t["evento"] == 1, t["data_cancelamento"], pd.Timestamp(C.CORTE) + pd.Timedelta(days=1))
    assert (t["data_troca_plano"] < pd.to_datetime(fim)).all()
    assert (t["data_troca_plano"] > t["data_inicio"] - pd.Timedelta(days=1)).all()


def test_mrr_inativo_zero_e_ativo_positivo(M):
    assert (M["mrr"][~M["ativo"]] == 0).all() and (M["mrr"][M["ativo"]] > 0).all()
    assert M["mrr"].shape[1] == len(O.fins_de_mes()) == 36


def test_mrr_aplica_promocao_black_friday_no_primeiro_mes(ev, M):
    # quem entrou pela Black Friday e estava ativo no 1º fim de mês paga 40% do preço de tabela
    bf = (ev["oferta_entrada"] == "black_friday").to_numpy()
    primeiro = np.where(M["ativo"].any(axis=1), M["ativo"].argmax(axis=1), -1)
    ok = bf & (primeiro >= 0) & (ev["plano_troca"].to_numpy() == "")
    idx = np.where(ok)[0][:200]
    for i in idx:
        t = primeiro[i]
        lista = C.PRECO_REAJUSTADO.get(ev["plano"].iloc[i], C.PRECO[ev["plano"].iloc[i]]) if M["reaj"][i, t] else C.PRECO[ev["plano"].iloc[i]]
        assert M["mrr"][i, t] == pytest.approx(lista * (1 - C.PROMO_DESCONTO))


def test_ponte_de_mrr_fecha_em_todos_os_meses(ponte, M):
    assert all(x["confere"] for x in ponte)
    for t, x in enumerate(ponte):
        assert x["final"] == pytest.approx(M["mrr"][:, t].sum(), abs=0.05)
        if t > 0:
            assert x["inicial"] == pytest.approx(ponte[t - 1]["final"], abs=0.05)
            comp = sum(x[k] for k in ("novo", "reativacao", "exp_upgrade", "exp_fim_promo", "exp_reajuste", "contracao", "churn"))
            assert x["inicial"] + comp == pytest.approx(x["final"], abs=0.1)


def test_sinais_dos_componentes_da_ponte(ponte):
    for x in ponte:
        assert x["novo"] >= 0 and x["reativacao"] >= 0 and x["exp_upgrade"] >= 0
        assert x["exp_fim_promo"] >= 0 and x["exp_reajuste"] >= 0
        assert x["contracao"] <= 0 and x["churn"] <= 0


def test_reajuste_so_aparece_no_mes_do_reajuste(ponte):
    meses = [x["mes"] for x in ponte]
    mes_reaj = C.REAJUSTE_INI.strftime("%Y-%m")
    for x in ponte:
        if x["mes"] == mes_reaj:
            assert x["exp_reajuste"] > 0
        else:
            assert x["exp_reajuste"] == 0, x["mes"]
    assert mes_reaj in meses


def test_fim_da_promocao_gera_expansao(ponte):
    assert sum(x["exp_fim_promo"] for x in ponte) > 0


def test_nrr_grr_limites_e_ic(df, ev, M):
    rr = O.retencao_receita(M, ev, n_boot=100)
    g = rr["global"]
    assert 0 < g["grr"] <= 1.0 and g["grr"] <= g["nrr"]
    assert g["nrr_lo"] <= g["nrr"] <= g["nrr_hi"] and g["grr_lo"] <= g["grr"] <= g["grr_hi"]
    assert set(rr["por_canal"]) == set(C.CANAIS) and set(rr["por_plano"]) == set(C.PLANOS)
    # o plano anual não tem expansão (preço mensal-equivalente fixo): NRR = GRR
    a = rr["por_plano"]["anual"]
    assert a["nrr"] == pytest.approx(a["grr"])
    # indicação retém mais receita que mídia paga (efeito plantado de permanência)
    assert rr["por_canal"]["indicacao"]["nrr"] > rr["por_canal"]["midia_paga"]["nrr"]


def test_reativacao_eleva_a_retencao_em_m12(ev, M):
    r = O.reativacao(ev, M)
    assert r["retencao_m12_com_reativacao"] > r["retencao_m12_primeiro_periodo"]
    assert r["ganho_retencao_m12"] == pytest.approx(r["retencao_m12_com_reativacao"] - r["retencao_m12_primeiro_periodo"])
    inv, vol = r["por_causa"]["involuntario"]["taxa"], r["por_causa"]["voluntario"]["taxa"]
    assert inv > vol                                   # quem sai por falha de pagamento volta mais


def test_funil_de_trial(ev):
    f = O.funil_trial(ev)
    por = {x["canal"]: x for x in f["canais"]}
    for c in C.CANAIS:
        x = por[c]
        assert x["trials"] >= x["convertidos"] == int((ev["canal"] == c).sum())
        assert x["lo"] <= x["conversao"] <= x["hi"]
        assert abs(x["conversao"] - C.TRIAL_CONVERSAO[c]) < 0.03
    assert f["global"]["convertidos"] == len(ev)
    assert por["indicacao"]["conversao"] > por["midia_paga"]["conversao"]


def test_funil_de_trial_e_deterministico(ev):
    assert O.funil_trial(ev) == O.funil_trial(ev)


def test_analise_completa_estrutura(df):
    a = O.analise(df, n_boot=50)
    assert a["ponte_confere"] and len(a["ponte"]) == 36
    u = a["ultimos_12m"]
    comp = sum(u[k] for k in ("novo", "reativacao", "exp_upgrade", "exp_fim_promo", "exp_reajuste", "contracao", "churn"))
    assert u["inicial"] + comp == pytest.approx(u["final"], rel=1e-6)
    assert u["expansao_total"] == pytest.approx(u["exp_upgrade"] + u["exp_fim_promo"] + u["exp_reajuste"])
    assert a["mrr_final"] == pytest.approx(a["arpu_final"] * a["ativos_final"], rel=1e-6)
