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
