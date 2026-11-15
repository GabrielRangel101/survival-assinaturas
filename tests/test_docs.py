"""Coerência entre results.json, os modelos e os documentos gerados (fonte única de números)."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from html.parser import HTMLParser

import nbformat
import pytest

from sobrevivencia import config as C
from sobrevivencia import docs, pipeline
from sobrevivencia import simulate as S
from sobrevivencia import templating as T

pytestmark = pytest.mark.docs

MODELOS = {
    "README.template.md": (False, C.RAIZ / "README.md"),
    "DECISIONS.template.md": (False, C.RAIZ / "DECISIONS.md"),
    "case.template.md": (False, C.PORTFOLIO_DIR / "case.md"),
    "card.template.txt": (False, C.PORTFOLIO_DIR / "card.txt"),
    "report.template.html": (True, docs.RELATORIO_HTML),
}


@pytest.fixture(scope="module")
def res():
    assert C.RESULTS_JSON.exists(), "rode `python run_all.py` antes dos testes de documentos"
    return T.carregar_resultados()


# ------------------------------------------------------------------------------------
# Nenhum número digitado à mão nos modelos
# ------------------------------------------------------------------------------------

@pytest.mark.parametrize("nome", list(MODELOS))
def test_modelos_nao_tem_numeros_digitados_a_mao(nome):
    html, _ = MODELOS[nome]
    texto = (C.TEMPLATES_DIR / nome).read_text(encoding="utf-8")
    assert T.numeros_digitados(texto, html=html) == []


# ------------------------------------------------------------------------------------
# Documentos em sincronia com results.json
# ------------------------------------------------------------------------------------

@pytest.mark.parametrize("nome", list(MODELOS))
def test_documento_gerado_e_identico_ao_renderizado_de_results(res, nome):
    _, saida = MODELOS[nome]
    extra = {"img": docs.imagens(), "dados_json": docs.dados_json(res)} if nome.endswith(".html") else None
    esperado = T.renderizar(nome, res, extra)
    atual = saida.read_text(encoding="utf-8")
    if nome == "card.template.txt":
        esperado = esperado.strip() + "\n"
    assert atual == esperado, f"{saida.name} está desatualizado: rode `python run_all.py`"


def test_demo_do_portfolio_e_copia_do_relatorio():
    demo = C.PORTFOLIO_DIR / "public" / "demos" / f"{docs.SLUG}.html"
    assert demo.read_bytes() == docs.RELATORIO_HTML.read_bytes()


def test_numeros_chave_aparecem_nos_tres_documentos(res):
    d = T.derivar(res)
    glob = res["ingenuo_vs_km"]["global"]["m12"]
    esperados = {
        "m12_km": T.f_pct(glob["valor"]),
        "n": T.f_int(res["dados"]["n"]),
        "hr_penhasco": T.f_hr(d["pen"]["hr"]),
        "ltv_cac_melhor": T.f_n(d["canal_melhor"]["ltv_cac"]["est"], 1),
        "cac_mais_barato": T.f_brl(d["canal_mais_barato"]["cac"]),
    }
    readme = (C.RAIZ / "README.md").read_text(encoding="utf-8")
    case = (C.PORTFOLIO_DIR / "case.md").read_text(encoding="utf-8")
    html = docs.RELATORIO_HTML.read_text(encoding="utf-8")
    for nome, valor in esperados.items():
        assert valor in readme, f"README sem {nome}={valor}"
        assert valor in html, f"relatório sem {nome}={valor}"
    for nome in ("m12_km", "n", "hr_penhasco", "ltv_cac_melhor", "cac_mais_barato"):
        assert esperados[nome] in case, f"case.md sem {nome}"


def test_numeros_dos_documentos_estao_em_results(res):
    """Todo percentual/R$ do README precisa poder ser reconstruído a partir de results.json."""
    texto = (C.RAIZ / "README.md").read_text(encoding="utf-8")
    texto = re.sub(r"```.*?```", " ", texto, flags=re.S)
    bruto = json.dumps(res)
    folhas = []

    def colhe(o):
        if isinstance(o, dict):
            for v in o.values():
                colhe(v)
        elif isinstance(o, list):
            for v in o:
                colhe(v)
        elif isinstance(o, (int, float)) and not isinstance(o, bool):
            folhas.append(float(o))

    colhe(res)
    folhas = sorted(set(folhas))
    import bisect

    def existe(x: float, tol: float) -> bool:
        i = bisect.bisect_left(folhas, x - tol)
        return i < len(folhas) and folhas[i] <= x + tol

    nao_achados = []
    for m in re.finditer(r"(\d{1,3}(?:\.\d{3})*(?:,\d+)?)\s*%", texto):
        v = float(m.group(1).replace(".", "").replace(",", ".")) / 100.0
        casas = len(m.group(1).split(",")[1]) if "," in m.group(1) else 0
        if not existe(v, 0.5 * 10 ** (-(casas + 2)) + 1e-12):
            nao_achados.append(m.group(0))
    assert not nao_achados, nao_achados
    assert bruto  # results.json não vazio


# ------------------------------------------------------------------------------------
# Relatório HTML autônomo
# ------------------------------------------------------------------------------------

class _Recursos(HTMLParser):
    def __init__(self):
        super().__init__()
        self.externos, self.links_css = [], []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "link":
            self.links_css.append(a)
        for k in ("src", "href"):
            v = a.get(k, "")
            if v.startswith(("http://", "https://", "//")) and tag != "a":
                self.externos.append((tag, v))


def test_relatorio_e_autonomo_sem_cdn_e_com_modo_noturno():
    html = docs.RELATORIO_HTML.read_text(encoding="utf-8")
    p = _Recursos()
    p.feed(html)
    assert p.externos == [] and p.links_css == []
    baixo = html.lower()
    for proibido in ("googleapis", "gstatic", "cdn.", "unpkg", "jsdelivr", "@import", "<link"):
        assert proibido not in baixo, proibido
    assert 'data-theme="dark"' in html and "prefers-color-scheme: dark" in html
    assert "localStorage" in html and "<script" in html
    assert html.count("data:image/png;base64,") >= 10          # figuras embutidas
    assert len(html.encode("utf-8")) < 5_000_000


def test_relatorio_tem_explorador_com_controles():
    html = docs.RELATORIO_HTML.read_text(encoding="utf-8")
    for id_ in ("exCanal", "exPlano", "exSafra", "exMeta", "exSvg", "metaB12", "metaB18", "metaB24", "chkNight"):
        assert f'id="{id_}"' in html
    for h in ("12", "18", "24"):
        assert f'data-h="{h}"' in html


def test_dados_embutidos_no_relatorio_batem_com_results(res):
    html = docs.RELATORIO_HTML.read_text(encoding="utf-8")
    m = re.search(r'<script id="dados" type="application/json">(.*?)</script>', html, flags=re.S)
    dados = json.loads(m.group(1).replace("<\\/", "</"))
    base = dados["explorador"]["curvas"]["todos|todos|todas"]
    glob = res["ingenuo_vs_km"]["global"]
    assert base["h"]["12"]["v"] == pytest.approx(glob["m12"]["valor"], abs=5e-5)
    assert base["h"]["24"]["ok"] is False
    assert dados["explorador"]["metas"] == {str(h): C.METAS[h] for h in C.HORIZONTES}
    assert len(dados["safras"]) == C.N_SAFRAS


# ------------------------------------------------------------------------------------
# Portfolio
# ------------------------------------------------------------------------------------

def test_card_tem_ate_250_caracteres():
    card = (C.PORTFOLIO_DIR / "card.txt").read_text(encoding="utf-8").strip()
    assert 50 < len(card) <= 250


def test_case_md_segue_o_formato_dos_cases_do_site():
    case = (C.PORTFOLIO_DIR / "case.md").read_text(encoding="utf-8")
    for secao in ("## Problema", "## Decisão", "## O que a análise mostra", "## Destaques",
                  "## Tecnologias utilizadas", "## Meu papel", "## Como foi feito", "## Limites"):
        assert secao in case
    assert "Projeto pessoal de análise estatística, com apoio de IA" in case
    assert "slug: sobrevivencia-assinaturas" in case and "categoria: Estatística aplicada" in case


def test_metadata_do_portfolio():
    meta = json.loads((C.PORTFOLIO_DIR / "metadata.json").read_text(encoding="utf-8"))
    assert meta["slug"] == "sobrevivencia-assinaturas" and meta["categoria"] == "Estatística aplicada"
    assert meta["demo_para"] == "public/demos/sobrevivencia-assinaturas.html"
    assert len(meta["card"]) <= 250


# ------------------------------------------------------------------------------------
# Integridade do conteúdo e dos resultados
# ------------------------------------------------------------------------------------

def _arquivos_de_texto():
    ignorar = {".git", "data", "__pycache__", ".pytest_cache", ".venv", "venv"}
    for p in C.RAIZ.rglob("*"):
        if p.is_file() and not (set(p.relative_to(C.RAIZ).parts) & ignorar) and p.suffix in {
                ".py", ".md", ".txt", ".json", ".html", ".yml", ".yaml", ".toml", ".ipynb", ""}:
            if p.name in {"test_docs.py", "RELATORIO_FINAL.md", "LICENSE"} or p.suffix == ".png":
                continue
            yield p


def test_nenhuma_mencao_a_empresa_real():
    proibidos = ["g" + "rupo r" + "bs", "r" + "bs", "g" + "zh", "zero " + "hora", "clic" + "rbs"]
    for p in _arquivos_de_texto():
        try:
            txt = p.read_text(encoding="utf-8").lower()
        except UnicodeDecodeError:
            continue
        txt = re.sub(r"data:image/[a-z]+;base64,[a-za-z0-9+/=]+", "", txt)
        txt = re.sub(r'"(?:s|h|lo|hi|nr|ev|n)":\[[^\]]*\]', "", txt)
        for termo in proibidos:
            assert not re.search(rf"\b{re.escape(termo)}\b", txt), f"{termo!r} em {p}"


def test_arquivos_em_utf8_sem_bom_e_sem_mojibake():
    for p in list((C.RAIZ).glob("*.md")) + list(C.PORTFOLIO_DIR.glob("*.*")) + [docs.RELATORIO_HTML]:
        b = p.read_bytes()
        assert not b.startswith(b"\xef\xbb\xbf"), p
        txt = b.decode("utf-8")
        assert "Ã§" not in txt and "Ã£" not in txt and "�" not in txt, p


def test_results_json_estrutura_e_coerencia_interna(res):
    for chave in ("premissas", "dados", "ingenuo_vs_km", "comparacoes", "cox", "valor", "decisao_verba",
                  "acao_mes3", "armadilhas", "riscos_competitivos", "explorador", "verdade", "meta"):
        assert chave in res
    assert res["dados"]["n_eventos"] + res["dados"]["n_censurados"] == res["dados"]["n"] == C.N_ASSINANTES
    assert res["premissas"]["metas"] == {f"m{h}": C.METAS[h] for h in C.HORIZONTES}
    assert res["ingenuo_vs_km"]["n_celulas_m24_preenchidas"] == 0
    assert res["cox"]["corrigido"]["ph_global"]["p"] > 0.05 > res["cox"]["ingenuo"]["ph_global"]["p"]


def test_ground_truth_json_confere_com_config():
    gt = json.loads(C.GROUND_TRUTH_JSON.read_text(encoding="utf-8"))
    assert gt["seed"] == C.SEED and gt["n"] == C.N_ASSINANTES
    assert gt["hr"]["canal"]["midia_paga"] == C.HR_CANAL["midia_paga"]
    assert gt["hr"]["promo_periodos"]["promo_penhasco"] == C.HR_PROMO_PERIODOS["promo_penhasco"]["hr"]


def test_n_testes_citado_nos_documentos_e_o_real(res):
    reais = pipeline.contar_testes()
    assert reais is not None
    assert res["meta"]["n_testes"] == reais, "rode `python run_all.py` de novo para atualizar a contagem"


def test_results_json_reproduzivel_do_zero(res):
    """Reexecuta a análise (mesma seed e mesmo n de bootstrap) e compara com o results.json gravado."""
    df, lat = S.simular()
    novo, _ = pipeline.montar_resultados(df, lat, res["premissas"]["n_boot"], com_riscos_competitivos=False,
                                         log=lambda *a: None, contar=False)
    novo = json.loads(pipeline.serializar(novo))

    def compara(a, b, caminho=""):
        if isinstance(a, dict):
            for k in a:
                if k in ("versoes", "n_testes"):
                    continue
                assert k in b, f"{caminho}/{k}"
                compara(a[k], b[k], f"{caminho}/{k}")
        elif isinstance(a, list):
            assert len(a) == len(b), caminho
            for i, (x, y) in enumerate(zip(a, b)):
                compara(x, y, f"{caminho}[{i}]")
        elif isinstance(a, float) or isinstance(b, float):
            assert a == pytest.approx(b, rel=1e-4, abs=1e-7), caminho
        else:
            assert a == b, caminho

    compara(novo, res)


# ------------------------------------------------------------------------------------
# Notebooks
# ------------------------------------------------------------------------------------

@pytest.mark.parametrize("nome", ["01_exploracao.ipynb", "02_analise.ipynb"])
def test_notebooks_executados_de_ponta_a_ponta_sem_erro(nome):
    nb = nbformat.read(str(C.NOTEBOOKS_DIR / nome), as_version=4)
    codigo = [c for c in nb.cells if c.cell_type == "code"]
    assert len(codigo) >= 8
    for c in codigo:
        assert c.execution_count is not None, "célula não executada"
        assert not any(o.get("output_type") == "error" for o in c.get("outputs", []))
    assert any(c.get("outputs") for c in codigo)


def test_run_all_expoe_ajuda():
    r = subprocess.run([sys.executable, str(C.RAIZ / "run_all.py"), "--help"], capture_output=True, text=True,
                       encoding="utf-8")
    assert r.returncode == 0 and "--sem-gate" in r.stdout
