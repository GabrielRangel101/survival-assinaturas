"""Validação em várias réplicas (versão pequena para rodar rápido na suíte)."""

from __future__ import annotations

import pytest

from sobrevivencia import montecarlo as M


@pytest.fixture(scope="module")
def mc():
    return M.recuperacao(n_rep=4, n=8000, log=lambda *a: None)


def test_estrutura_e_contagem(mc):
    assert mc["n_replicas"] == 4
    assert len(mc["efeitos"]) == 13          # efeitos com razão única plantada
    assert mc["n_intervalos"] == 4 * 13


def test_media_dos_hr_estimados_perto_do_plantado_nos_efeitos_fortes(mc):
    por = {e["nome"]: e for e in mc["efeitos"]}
    for nome in ("canal_midia_paga", "canal_indicacao", "eng_z", "promo_penhasco", "reajuste_exposto"):
        assert abs(por[nome]["vies_rel"]) < 0.15, (nome, por[nome])


def test_cobertura_dos_intervalos_razoavel(mc):
    assert 0.8 <= mc["cobertura_total"] <= 1.0
    assert all(0.0 <= e["cobertura"] <= 1.0 for e in mc["efeitos"])


def test_replicas_deterministicas():
    a = M.recuperacao(n_rep=1, n=4000, log=lambda *x: None)
    b = M.recuperacao(n_rep=1, n=4000, log=lambda *x: None)
    assert a == b


def test_robustez_tem_tres_variantes_e_o_penhasco_deslocado_piora_a_cobertura():
    r = M.robustez(n_rep=2, n=5000, log=lambda *a: None)
    assert [v["id"] for v in r["variantes"]] == ["oficial", "fragilidade", "penhasco_deslocado"]
    for v in r["variantes"]:
        assert 0.0 <= v["cobertura_total"] <= 1.0 and v["vies_abs_max"] >= 0
        assert [e["nome"] for e in v["efeitos"]] == list(M.ROB_EFEITOS)
    por = {v["id"]: v for v in r["variantes"]}
    # com o efeito fora do mês que o modelo supõe, o pós-penhasco fica visivelmente viesado
    pos = {e["nome"]: e for e in por["penhasco_deslocado"]["efeitos"]}["promo_pos"]
    assert abs(pos["vies_rel"]) > 0.15
    assert por["penhasco_deslocado"]["vies_abs_max"] > por["oficial"]["vies_abs_max"]
