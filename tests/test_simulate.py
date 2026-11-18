"""Determinismo da seed e invariantes de censura do gerador de dados."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from sobrevivencia import config as C
from sobrevivencia import simulate as S


def test_determinismo_mesma_seed_mesmos_dados(df):
    df2, _ = S.simular(seed=C.SEED)
    pd.testing.assert_frame_equal(df, df2)


def test_seed_diferente_muda_os_dados(df):
    df3, _ = S.simular(seed=C.SEED + 1)
    assert not df["duracao_meses"].equals(df3["duracao_meses"])


def test_tamanho_e_janela_de_entrada(df):
    assert len(df) == C.N_ASSINANTES
    assert df["data_inicio"].min() >= pd.Timestamp(C.ENTRADA_INI)
    assert df["data_inicio"].max() <= pd.Timestamp(C.ENTRADA_FIM)
    assert df["id_assinante"].is_unique


def test_duracoes_positivas_e_nao_negativas(df):
    assert (df["duracao_meses"] >= 0).all()
    assert (df["duracao_meses"] > 0).all()  # exposição mínima de 1 dia
    assert df["duracao_meses"].max() <= df["seguimento_max_meses"].max() + 1e-9


def test_nenhum_evento_apos_o_corte(df):
    cancel = df.loc[df["evento"] == 1, "data_cancelamento"]
    assert cancel.notna().all()
    assert (cancel <= pd.Timestamp(C.CORTE)).all()
    # censurados não têm data de cancelamento nem causa
    cens = df[df["evento"] == 0]
    assert cens["data_cancelamento"].isna().all()
    assert (cens["causa"] == "").all()


def test_duracao_nunca_excede_seguimento_possivel(df):
    assert (df["duracao_meses"] <= df["seguimento_max_meses"] + 1e-9).all()
    cens = df[df["evento"] == 0]
    # censurado: duração = seguimento possível (observado até o corte)
    np.testing.assert_allclose(cens["duracao_meses"], cens["seguimento_max_meses"], atol=1e-5)


def test_cancelamento_apos_inicio(df):
    ev = df[df["evento"] == 1]
    assert (ev["data_cancelamento"] >= ev["data_inicio"]).all()


def test_ha_censura_e_eventos_e_tres_causas(df):
    assert 0.2 < df["evento"].mean() < 0.5
    assert set(df.loc[df["evento"] == 1, "causa"]) == set(C.CAUSAS)


def test_valores_categoricos_validos(df):
    assert set(df["canal"]) <= set(C.CANAIS)
    assert set(df["plano"]) <= set(C.PLANOS)
    assert set(df["oferta_entrada"]) <= set(C.OFERTAS)
    assert df["engajamento_pre"].between(0, 100).all()
    # Black Friday só para quem não é anual; Passe Copa só na janela da Copa
    assert not ((df["plano"] == "anual") & (df["oferta_entrada"] != "nenhuma")).any()
    copa = df[df["oferta_entrada"] == "passe_copa"]["data_inicio"]
    ini, fim, _ = C.CAMPANHAS["passe_copa_2026"]
    assert copa.between(pd.Timestamp(ini), pd.Timestamp(fim)).all()


def test_anual_cancela_principalmente_na_renovacao(df):
    ev = df[(df["plano"] == "anual") & (df["evento"] == 1)]
    na_renovacao = (ev["duracao_meses"] >= 12).mean()
    assert na_renovacao > 0.7


def test_ground_truth_gravado_e_consistente(df, latente, tmp_path):
    gt = S.construir_ground_truth(df, latente)
    assert gt["seed"] == C.SEED
    assert gt["hr"]["canal"]["midia_paga"] == C.HR_CANAL["midia_paga"] > 1
    assert gt["hr"]["canal"]["indicacao"] < 1
    assert gt["hr"]["engajamento_por_dp"] < 1
    assert gt["hr"]["passe_copa"] > 1
    penh = gt["hr"]["promo_periodos"]["promo_penhasco"]
    assert penh > gt["hr"]["promo_periodos"]["promo_vigente"]
    s12 = gt["sobrevivencia_verdade"]["global"]["m12"]["todos"]
    assert 0.5 < s12 < 0.8


def test_safras_cobrem_toda_a_janela(df):
    assert set(df["safra"]) == set(S.SAFRAS)
    assert len(S.rotulo_safra(1)) > 5


def test_black_friday_de_cada_ano_aparece_na_janela_de_36_meses(df):
    assert C.ENTRADA_INI.year == 2023 and (C.ENTRADA_FIM - C.ENTRADA_INI).days > 1000
    for nome in ("black_friday_2023", "black_friday_2024", "black_friday_2025"):
        ini, fim, _ = C.CAMPANHAS[nome]
        s = df[(df["oferta_entrada"] == "black_friday") & df["data_inicio"].between(pd.Timestamp(ini), pd.Timestamp(fim))]
        assert len(s) > 100, nome


def test_safras_sao_doze_trimestres_a_partir_da_primeira_entrada(df):
    assert len(S.SAFRAS) == C.N_SAFRAS == 12
    assert df.loc[df["data_inicio"] < pd.Timestamp("2024-02-01"), "safra"].eq("S1").all()
    assert df.loc[df["data_inicio"] >= pd.Timestamp("2026-08-01"), "safra"].eq("S12").all()
    assert S.rotulo_safra(1) == "Nov/23–Jan/24" and S.rotulo_safra(12) == "Ago/26–Out/26"


def test_m24_e_observavel_com_a_janela_de_36_meses(df):
    assert (df["seguimento_max_meses"] >= 24).sum() > 3000


def test_variante_oficial_nao_muda_e_variantes_mantem_as_covariaveis():
    a, _ = S.simular(seed=C.SEED + 7, n=3000)
    b, _ = S.simular(seed=C.SEED + 7, n=3000, fragilidade=0.0, desloc_penhasco_dias=0.0)
    pd.testing.assert_frame_equal(a, b)
    c, _ = S.simular(seed=C.SEED + 7, n=3000, fragilidade=0.5)
    for col in ("data_inicio", "canal", "plano", "oferta_entrada", "dispositivo", "engajamento_pre"):
        assert a[col].equals(c[col]), col
    assert not a["duracao_meses"].equals(c["duracao_meses"])


def test_fragilidade_tem_media_um_e_a_variancia_pedida():
    _, l0 = S.simular(seed=C.SEED + 8, n=20000)
    _, l1 = S.simular(seed=C.SEED + 8, n=20000, fragilidade=0.5)
    razao = l1.taxa_mes_ref / l0.taxa_mes_ref
    assert razao.mean() == pytest.approx(1.0, abs=0.03)
    assert razao.var() == pytest.approx(0.5, abs=0.06)


def test_penhasco_deslocado_move_o_efeito_por_periodo():
    sub = pd.DataFrame({"plano": ["mensal"], "oferta_entrada": ["black_friday"],
                        "data_inicio": [pd.Timestamp("2023-11-25")]})
    n_dias = int(np.ceil(C.MESES_LATENTES * C.DIAS_POR_MES))
    h0 = S._taxas_diarias(sub, np.ones(1), 0, 1, n_dias)[0]
    h1 = S._taxas_diarias(sub, np.ones(1), 0, 1, n_dias, desloc_dias=15.0)[0]
    pen, vig, pos = (C.HR_PROMO_PERIODOS[k]["hr"] for k in ("promo_penhasco", "promo_vigente", "promo_pos"))
    assert h0[100] / h1[100] == pytest.approx(pen / vig)      # oficial: penhasco (mês 3-4); deslocado: ainda vigente
    assert h1[125] / h0[125] == pytest.approx(pen / pos)      # oficial: pós-penhasco; deslocado: penhasco
    assert h1[5] / h0[5] == pytest.approx(1.0 / vig)          # nos primeiros dias o deslocado ainda não tem desconto de risco
