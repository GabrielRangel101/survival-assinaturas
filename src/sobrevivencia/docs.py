"""Gera os documentos (README, DECISIONS, relatório HTML, portfolio/) a partir de results.json."""

from __future__ import annotations

import base64
import json
import shutil
from pathlib import Path

from markupsafe import Markup

from . import config as C
from . import templating as T

SLUG = "sobrevivencia-assinaturas"
CATEGORIA = "Estatística aplicada"
RELATORIO_HTML = C.REPORT_DIR / f"{SLUG}.html"


def _data_uri(p: Path) -> Markup:
    b64 = base64.b64encode(p.read_bytes()).decode("ascii")
    return Markup(f"data:image/png;base64,{b64}")


def imagens(pasta: Path = C.FIGURES_DIR) -> dict[str, Markup]:
    nomes = {
        "ingenua_vs_km": "01_ingenua_vs_km.png", "km_canal": "02_km_canal.png", "km_plano": "03_km_plano.png",
        "penhasco": "04_penhasco.png", "forest": "05_cox_forest.png", "schoenfeld": "06_schoenfeld.png",
        "valor": "07_valor_canal.png", "payback": "08_payback.png", "armadilhas": "09_armadilhas.png",
        "riscos_competitivos": "10_riscos_competitivos.png", "decisao": "11_decisao.png",
        "realocacao": "12_realocacao.png", "mrr": "13_mrr.png", "fora_do_tempo": "14_fora_do_tempo.png",
        "externo": "15_dataset_publico.png",
    }
    return {k: _data_uri(pasta / v) for k, v in nomes.items() if (pasta / v).exists()}


def dados_json(res: dict) -> Markup:
    """Dados embutidos no relatório (explorador + tabela de safras editável)."""
    safras = []
    for l in res["ingenuo_vs_km"]["safras"]:
        safras.append({
            "safra": l["safra"], "rotulo": res["premissas"]["rotulos"]["safra"][l["safra"]], "n": l["n"],
            "ret_ingenua": l["ret_ingenua"],
            "horizontes": {k: {"ok": v["ok"], "valor": v["valor"], "lo": v["lo"], "hi": v["hi"], "motivo": v["motivo"]}
                           for k, v in l["horizontes"].items() if k in ("m3", "m12", "m18", "m24")},
        })
    txt = json.dumps({"explorador": res["explorador"], "safras": safras}, ensure_ascii=False, separators=(",", ":"))
    return Markup(txt.replace("</", "<\\/"))


def construir(res: dict | None = None) -> dict[str, Path]:
    """Renderiza todos os documentos. Devolve {nome: caminho}."""
    res = res or T.carregar_resultados()
    saidas: dict[str, Path] = {}
    C.PORTFOLIO_DIR.mkdir(parents=True, exist_ok=True)
    C.REPORT_DIR.mkdir(parents=True, exist_ok=True)

    def grava(caminho: Path, texto: str) -> None:
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text(texto, encoding="utf-8", newline="\n")

    grava(C.RAIZ / "README.md", T.renderizar("README.template.md", res))
    saidas["README.md"] = C.RAIZ / "README.md"
    grava(C.RAIZ / "DECISIONS.md", T.renderizar("DECISIONS.template.md", res))
    saidas["DECISIONS.md"] = C.RAIZ / "DECISIONS.md"
    grava(C.RAIZ / "GUIA_DE_DEFESA.md", T.renderizar("GUIA_DEFESA.template.md", res))
    saidas["GUIA_DE_DEFESA.md"] = C.RAIZ / "GUIA_DE_DEFESA.md"
    grava(C.PORTFOLIO_DIR / "case.md", T.renderizar("case.template.md", res))
    saidas["case.md"] = C.PORTFOLIO_DIR / "case.md"
    card = T.renderizar("card.template.txt", res).strip()
    grava(C.PORTFOLIO_DIR / "card.txt", card + "\n")
    saidas["card.txt"] = C.PORTFOLIO_DIR / "card.txt"

    html = T.renderizar("report.template.html", res, {"img": imagens(), "dados_json": dados_json(res)})
    grava(RELATORIO_HTML, html)
    saidas["relatorio"] = RELATORIO_HTML
    demo = C.PORTFOLIO_DIR / "public" / "demos" / f"{SLUG}.html"
    demo.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(RELATORIO_HTML, demo)
    saidas["demo"] = demo
    # página online (GitHub Pages serve a pasta docs/ da branch main)
    pagina = C.RAIZ / "docs" / "index.html"
    pagina.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(RELATORIO_HTML, pagina)
    (C.RAIZ / "docs" / ".nojekyll").write_text("", encoding="utf-8")
    saidas["pagina_online"] = pagina

    meta = {
        "slug": SLUG, "categoria": CATEGORIA, "card": card, "tecnologias": ["Python", "pandas", "lifelines"],
        "tipo_de_dado": "Sintético", "meu_papel": "Projeto pessoal de análise estatística, com apoio de IA",
        "demo_para": f"public/demos/{SLUG}.html", "demo_url": f"/demos/{SLUG}.html",
        "repositorio": "https://github.com/GabrielRangel101/survival-assinaturas",
        "titulo": "Sobrevivência de assinantes: onde a retenção quebra",
    }
    grava(C.PORTFOLIO_DIR / "metadata.json", json.dumps(meta, ensure_ascii=False, indent=2) + "\n")
    saidas["metadata.json"] = C.PORTFOLIO_DIR / "metadata.json"
    return saidas


if __name__ == "__main__":  # python -m sobrevivencia.docs
    for k, v in construir().items():
        print(f"{k}: {v}")
