"""Dataset público de churn: integridade do arquivo e o que o pipeline encontra nele."""

from __future__ import annotations

import pytest

from sobrevivencia import externo as E


@pytest.fixture(scope="module")
def d():
    return E.carregar()


@pytest.fixture(scope="module")
def r(d):
    return E.analise(d)


def test_arquivo_confere_com_o_sha256_e_a_licenca_esta_documentada():
    assert E.conferir_arquivo()
    leia = (E.ARQUIVO.parent / "LEIA-ME.md").read_text(encoding="utf-8")
    assert E.SHA256 in leia and "Apache-2.0" in leia and "não é um dado de operação real" in leia


def test_arquivo_adulterado_e_recusado(monkeypatch):
    monkeypatch.setattr(E, "SHA256", "0" * 64)
    with pytest.raises(ValueError):
        E.carregar()


def test_carga_exclui_so_os_clientes_sem_cobranca(d):
    assert len(d) == 7032 and d["evento"].sum() == 1869
    assert d["duracao"].min() >= 1 and d["duracao"].max() == 72


def test_contagens_e_km_ordenados_por_tipo_de_contrato(r):
    g = {x["chave"]: x for x in r["contrato"]["grupos"]}
    assert sum(x["n"] for x in g.values()) == r["dados"]["n"]
    m12 = {k: v["horizontes"]["m12"]["valor"] for k, v in g.items()}
    assert m12["Month-to-month"] < m12["One year"] < m12["Two year"] <= 1.0
    assert r["contrato"]["logrank"]["p"] < 1e-10
    assert all(x["significativo_holm"] for x in r["contrato"]["pares"])
    for x in g.values():
        for p in x["horizontes"].values():
            if p["ok"]:
                assert p["lo"] <= p["valor"] <= p["hi"] and p["n_risco"] >= 30


def test_primeiro_mes_concentra_cancelamentos(r):
    pm = r["primeiro_mes"]
    assert 0.1 < pm["pct_de_todos_cancelamentos"] < 0.4
    assert pm["taxa_contrato_mensal"] > pm["taxa"]
    faixas = r["taxa_por_faixa"]
    assert faixas[0]["Month-to-month"] > faixas[3]["Month-to-month"]     # o risco do mensal cai depois do 1º mês


def test_cox_ingenuo_viola_riscos_proporcionais(r):
    c = r["cox"]["ingenuo"]
    assert c["ph_global"]["p"] < 1e-6 and c["n_viola"] >= 3
    hr = {x["nome"]: x["hr"] for x in c["coefs"]}
    assert hr["contrato_2anos"] < hr["contrato_1ano"] < 1.0
    assert hr["internet_fibra"] > 1.5 and hr["cheque_eletronico"] > 1.2


def test_correcao_por_estrato_nao_basta_neste_dataset(r):
    """Achado que não foi plantado: no sintético a estratificação resolve; aqui o teste ainda rejeita covariáveis."""
    c = r["cox"]["corrigido"]
    assert c["n_viola"] > 0 and c["ph_global"]["p"] < 0.05
    assert not any(x["nome"].startswith("contrato_") for x in c["coefs"])    # o contrato virou estrato


def test_leitura_de_periodo_e_incoerente_com_o_arquivo(r):
    assert r["leitura_periodo"]["m12"] < 0.01       # quase ninguém sobreviveria a 12 meses, mas há clientes de 72


def test_analise_e_deterministica(d, r):
    assert E.analise(d) == r
