"""Safras (ingênuo x Kaplan-Meier), regras de observabilidade, comparações e explorador."""

from __future__ import annotations

import pytest

from sobrevivencia import cohorts as H
from sobrevivencia import config as C


@pytest.fixture(scope="module")
def tab(df):
    return H.tabela_safras(df)


@pytest.fixture(scope="module")
def comp(df):
    return H.comparacoes(df)


def test_desenho_contagens_batem(df):
    r = H.resumo_dados(df)
    assert r["n"] == C.N_ASSINANTES
    assert r["n_eventos"] + r["n_censurados"] == r["n"]
    assert sum(r["causas"].values()) == r["n_eventos"]
    assert sum(r["por_canal"].values()) == r["n"]
    assert r["n_com_24m_possiveis"] == 0           # ninguém tem 24 meses completos de observação
    assert r["seguimento_max_meses"] < 24.1


def test_celulas_sem_tempo_de_observacao_ficam_vazias(tab):
    por_safra = {l["safra"]: l["horizontes"] for l in tab["safras"]}
    # M12 só para as safras S1-S4; M18 só para S1-S2; M24 para nenhuma
    for s in ("S1", "S2", "S3", "S4"):
        assert por_safra[s]["m12"]["ok"] and por_safra[s]["m12"]["valor"] is not None
    for s in ("S5", "S6", "S7", "S8"):
        assert not por_safra[s]["m12"]["ok"] and por_safra[s]["m12"]["valor"] is None
    assert [s for s, h in por_safra.items() if h["m18"]["ok"]] == ["S1", "S2"]
    assert not any(h["m24"]["ok"] for h in por_safra.values())
    assert tab["n_celulas_m24_preenchidas"] == 0
    # células vazias não carregam número, nem IC, nem status de meta
    vazia = por_safra["S8"]["m12"]
    assert vazia["lo"] is None and vazia["hi"] is None and vazia["status"] is None and vazia["motivo"]


def test_km_dentro_do_ic_e_entre_zero_e_um(tab):
    for l in tab["safras"]:
        for p in l["horizontes"].values():
            if p["ok"]:
                assert 0 < p["lo"] <= p["valor"] <= p["hi"] < 1


def test_retencao_ingenua_depende_da_idade_da_safra(tab):
    # ativos/iniciados cresce monotonicamente das safras antigas para as recentes (artefato)
    ing = [l["ret_ingenua"] for l in tab["safras"]]
    assert all(a < b for a, b in zip(ing, ing[1:]))
    assert tab["rho_ingenua_idade"] == pytest.approx(-1.0)
    # o KM em M3 (comparável entre safras) conta outra história: as recentes NÃO são melhores
    km3 = [l["horizontes"]["m3"]["valor"] for l in tab["safras"] if l["horizontes"]["m3"]["ok"]]
    assert km3[-1] < km3[0]
    assert tab["rho_km_m3_idade"] > 0


def test_status_vs_meta_coerente(tab):
    for l in tab["safras"]:
        for h in C.HORIZONTES:
            p = l["horizontes"][f"m{h}"]
            if not p["ok"]:
                assert p["status"] is None
            elif p["status"] == "abaixo":
                assert p["hi"] < C.METAS[h]
            elif p["status"] == "acima":
                assert p["lo"] > C.METAS[h]
            else:
                assert p["lo"] <= C.METAS[h] <= p["hi"]


def test_logrank_detecta_diferencas_planejadas(comp):
    assert comp["canal"]["logrank"]["p"] < 1e-10 and comp["canal"]["logrank"]["df"] == 5
    assert comp["plano"]["logrank"]["p"] < 1e-10 and comp["plano"]["logrank"]["df"] == 3
    assert comp["safra"]["logrank"]["p"] < 0.01 and comp["safra"]["logrank"]["df"] == 7


def test_pares_e_holm(comp):
    assert comp["canal"]["n_pares"] == 15 and comp["plano"]["n_pares"] == 6 and comp["safra"]["n_pares"] == 28
    for nome in ("canal", "plano", "safra"):
        c = comp[nome]
        assert c["n_sig_holm"] <= c["n_sig_bruto"]
        for x in c["pares"]:
            assert x["p_holm"] >= x["p"]
    # Holm derruba parte das 28 comparações brutas entre safras
    assert comp["safra"]["n_sig_holm"] < comp["safra"]["n_sig_bruto"]


def test_km_recupera_sobrevivencia_verdadeira_por_grupo(comp, gt):
    cobre, n = 0, 0
    for nome, mapa in (("canal", gt["sobrevivencia_verdade"]["por_canal"]),
                       ("plano", gt["sobrevivencia_verdade"]["por_plano"])):
        for g in comp[nome]["grupos"]:
            for h in (12, 18):
                p = g["horizontes"][f"m{h}"]
                if not p["ok"]:
                    continue
                verdade = mapa[g["chave"]][f"m{h}"]["todos"]
                assert abs(p["valor"] - verdade) < 0.06
                cobre += int(p["lo"] <= verdade <= p["hi"])
                n += 1
    assert n == 20 and cobre / n >= 0.85


def test_explorador_cobre_todas_as_combinacoes(df):
    ex = H.explorador(df)
    assert "todos|todos|todas" in ex["curvas"]
    base = ex["curvas"]["todos|todos|todas"]
    assert base["n"] == len(df) and len(base["S"]) == 25
    assert base["S"][0] == 1.0 and all(a >= b for a, b in zip(base["S"], base["S"][1:]))
    assert all(l <= s <= h for l, s, h in zip(base["lo"], base["S"], base["hi"]))
    # M24 não é observável em lugar nenhum; M12 pooled é
    assert not base["h"]["24"]["ok"] and base["h"]["12"]["ok"]
    # safra sem tempo de observação fica vazia mesmo havendo gente sob risco parcial
    assert not ex["curvas"]["todos|todos|S8"]["h"]["12"]["ok"]
    assert len(ex["curvas"]) > 250
