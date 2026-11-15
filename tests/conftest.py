"""Fixtures compartilhadas (dados simulados uma única vez por sessão de testes)."""

from __future__ import annotations

import pytest

from sobrevivencia import simulate as S


@pytest.fixture(scope="session")
def sim():
    """(df, latente) com a seed oficial."""
    return S.simular()


@pytest.fixture(scope="session")
def df(sim):
    return sim[0]


@pytest.fixture(scope="session")
def latente(sim):
    return sim[1]


@pytest.fixture(scope="session")
def gt(df, latente):
    return S.construir_ground_truth(df, latente)
