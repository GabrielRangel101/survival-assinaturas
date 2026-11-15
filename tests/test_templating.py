"""Filtros pt-BR e o detector de números digitados à mão (não dependem de results.json)."""

from __future__ import annotations

import pytest

from sobrevivencia import templating as T


def test_filtros_pt_br():
    assert T.f_int(12000) == "12.000"
    assert T.f_n(3.14159, 2) == "3,14"
    assert T.f_pct(0.6612) == "66,1%"
    assert T.f_pct(0.65, 0) == "65%"
    assert T.f_brl(1234.4) == "R$ 1.234"
    assert T.f_brl(-12.5, 2) == "−R$ 12,50"
    assert T.f_brl_mi(444_300) == "R$ 444,3 mil"
    assert T.f_brl_mi(1_800_000) == "R$ 1,80 milhões"
    assert T.f_p(0.0000001) == "< 0,001" and T.f_p(0.0123) == "0,012"
    assert T.f_hr(2.8545) == "2,85"
    assert T.f_data("2026-10-31") == "31/10/2026"
    assert T.f_mes_ano("2024-11-01") == "novembro de 2024"
    assert T.f_sn(-1.0, 2) == "−1,00" and T.f_sn(0.5, 1) == "+0,5"
    assert T.f_pp(0.0123) == "+1,2 p.p." and T.f_pp_abs(-0.0345) == "3,5 p.p."


def test_detector_pega_numero_solto_e_ignora_placeholders():
    assert T.numeros_digitados("A retenção foi de 66,1% em M12.")
    assert T.numeros_digitados("Custa R$ 52 por assinante.")
    assert T.numeros_digitados("Foram 12000 assinantes.")
    assert T.numeros_digitados("HR de 2,85.")
    assert T.numeros_digitados("A retenção foi {{ x|pct }} em M12 e M18.") == []
    assert T.numeros_digitados("{% for a in b %}{{ a }}{% endfor %} Python 3.13, 2026, IC 95% e M24.") == []
    assert T.numeros_digitados("Comando: `pip install x==1.2` e\n```\nrun 12,5\n```\n") == []


def test_detector_em_html_ignora_estilo_script_e_atributos():
    html = '<style>a{width:12.5px}</style><div class="x-1.5" data-v="66,1%">texto {{ a }}</div><script>var x=3.14;</script>'
    assert T.numeros_digitados(html, html=True) == []
    assert T.numeros_digitados("<p>texto 66,1%</p>", html=True)


def test_strict_undefined_falha_em_chave_inexistente(tmp_path):
    (tmp_path / "t.md").write_text("{{ nao_existe.valor|pct }}", encoding="utf-8")
    with pytest.raises(Exception):
        T.renderizar("t.md", {}, pasta=tmp_path)
