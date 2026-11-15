"""Motor de templates: TODO número dos documentos vem de results.json via filtros pt-BR.

Os templates (templates/*) não contêm números digitados à mão; um teste confere isso.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from . import config as C

_MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro",
          "outubro", "novembro", "dezembro"]


# ------------------------------------------------------------------------------------
# Filtros de formatação (pt-BR)
# ------------------------------------------------------------------------------------

def _dec(x: float, d: int) -> str:
    return f"{x:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def f_int(x) -> str:
    return _dec(float(x), 0)


def f_n(x, d: int = 1) -> str:
    return _dec(float(x), int(d))


def f_sn(x, d: int = 1) -> str:
    """Número com sinal explícito."""
    v = float(x)
    s = _dec(abs(v), int(d))
    return ("+" if v >= 0 else "−") + s


def f_pct(x, d: int = 1) -> str:
    return _dec(float(x) * 100, int(d)) + "%"


def f_pp(x, d: int = 1) -> str:
    """Diferença entre proporções, em pontos percentuais, com sinal."""
    v = float(x) * 100
    return ("+" if v >= 0 else "−") + _dec(abs(v), int(d)) + " p.p."


def f_pp_abs(x, d: int = 1) -> str:
    return _dec(abs(float(x)) * 100, int(d)) + " p.p."


def f_brl(x, d: int = 0) -> str:
    v = float(x)
    return ("−" if v < 0 else "") + "R$ " + _dec(abs(v), int(d))


def f_brl_mi(x) -> str:
    v = float(x)
    if abs(v) >= 1e6:
        return "R$ " + _dec(v / 1e6, 2) + " milhões"
    if abs(v) >= 1e3:
        return "R$ " + _dec(v / 1e3, 1) + " mil"
    return "R$ " + _dec(v, 0)


def f_p(x) -> str:
    v = float(x)
    if v < 0.001:
        return "< 0,001"
    return _dec(v, 3)


def f_hr(x) -> str:
    return _dec(float(x), 2)


def f_data(s: str) -> str:
    y, m, d = (int(p) for p in s.split("-"))
    return f"{d:02d}/{m:02d}/{y}"


def f_mes_ano(s: str) -> str:
    y, m, _ = (int(p) for p in s.split("-"))
    return f"{_MESES[m - 1]} de {y}"


def f_cap(s: str) -> str:
    return s[:1].upper() + s[1:]


FILTROS = {
    "int": f_int, "n": f_n, "sn": f_sn, "pct": f_pct, "pp": f_pp, "ppa": f_pp_abs, "brl": f_brl,
    "brl_mi": f_brl_mi, "p": f_p, "hr": f_hr, "data": f_data, "mes_ano": f_mes_ano, "cap": f_cap,
}


def ambiente(pasta: Path = C.TEMPLATES_DIR) -> Environment:
    env = Environment(loader=FileSystemLoader(str(pasta)), undefined=StrictUndefined,
                      autoescape=select_autoescape(["html"]), trim_blocks=True, lstrip_blocks=True,
                      keep_trailing_newline=True)
    env.filters.update(FILTROS)
    return env


# ------------------------------------------------------------------------------------
# Contexto derivado (apenas seleciona/ordena/rotula valores já presentes no results.json)
# ------------------------------------------------------------------------------------

def carregar_resultados(caminho: Path = C.RESULTS_JSON) -> dict:
    return json.loads(Path(caminho).read_text(encoding="utf-8"))


def derivar(res: dict) -> dict:
    """Seleções derivadas dos resultados (nomes, rankings, sinais) para o texto dos documentos."""
    rot = res["premissas"]["rotulos"]
    canais = {c["canal"]: c for c in res["valor"]["canais"]}
    rank_ltv = res["valor"]["ranking_ltv_cac"]
    rank_cac = res["valor"]["ranking_cac"]
    dv = res["decisao_verba"]
    cox = res["cox"]
    por_c = {r["nome"]: r for r in cox["corrigido"]["coefs"]}
    por_i = {r["nome"]: r for r in cox["ingenuo"]["coefs"]}
    tab = res["ingenuo_vs_km"]
    comp = res["comparacoes"]
    km_canal = {g["chave"]: g for g in comp["canal"]["grupos"]}
    km_plano = {g["chave"]: g for g in comp["plano"]["grupos"]}
    # canal de maior e menor retenção em M12 (KM)
    ordem_m12 = sorted(km_canal.values(), key=lambda g: -g["horizontes"]["m12"]["valor"])
    ordem_rmst = sorted(res["valor"]["canais"], key=lambda c: -c["rmst"]["est"])
    ph_i = {r["nome"]: r for r in cox["ingenuo"]["ph"]}
    ph_c = {r["nome"]: r for r in cox["corrigido"]["ph"]}
    acao = res["acao_mes3"]
    d = {
        "rot": rot,
        "canais": canais,
        "melhor_m12": ordem_m12[0], "pior_m12": ordem_m12[-1],
        "melhor_rmst": ordem_rmst[0], "pior_rmst": ordem_rmst[-1],
        "rank_ltv_cac": [canais[c] for c in rank_ltv],
        "rank_cac": [canais[c] for c in rank_cac],
        "canal_melhor": canais[dv["melhor"]], "canal_pior": canais[dv["pior"]],
        "canal_mais_barato": canais[dv["mais_barato"]], "canal_midia": canais["midia_paga"],
        "canal_busca": canais["busca_paga"], "canal_social": canais["social"], "canal_indicacao": canais["indicacao"],
        "canais_nao_escalaveis": [c for c in res["valor"]["canais"] if not c["escalavel"]],
        "linha_melhor": next(l for l in dv["linhas"] if l["canal"] == dv["melhor"]),
        "linha_pior": next(l for l in dv["linhas"] if l["canal"] == dv["pior"]),
        "linha_midia": next(l for l in dv["linhas"] if l["canal"] == "midia_paga"),
        "km_canal": km_canal, "km_plano": km_plano,
        "coef": por_c, "coef_ing": por_i, "ph_i": ph_i, "ph_c": ph_c,
        "hr_bf": por_i["oferta_bf"],
        "inverte": bool(res["valor"]["rank_inverte"]),
        "rank_cac_primeiro": canais[rank_cac[0]],
        "pen": acao["medido"]["periodos"]["promo_penhasco"],
        "pos": acao["medido"]["periodos"]["promo_pos"],
        "proj": acao["projetado"],
        "safras": tab["safras"],
        "glob": tab["global"],
        "n_safras_abaixo": sum(1 for l in tab["safras"] for h in ("m12", "m18")
                               if l["horizontes"][h]["status"] == "abaixo"),
        "n_safras_acima": sum(1 for l in tab["safras"] for h in ("m12", "m18")
                              if l["horizontes"][h]["status"] == "acima"),
        "ingenua_melhor": max(tab["safras"], key=lambda l: l["ret_ingenua"]),
        "ingenua_pior": min(tab["safras"], key=lambda l: l["ret_ingenua"]),
        "meta": res["premissas"]["metas"],
        "metodos_censura": {m["id"]: m for m in res["armadilhas"]["censura"]["metodos"]},
        "rc": res.get("riscos_competitivos"),
        "km_cobre_n": sum(1 for r in res["km_vs_verdade"] if r["cobre"]),
        "payback_min": min(c["payback"]["est"] for c in res["valor"]["canais"]),
        "payback_max": max(c["payback"]["est"] for c in res["valor"]["canais"]),
        "censura_erro_max": max(abs(m["erro_pp"]) for m in res["armadilhas"]["censura"]["metodos"]
                                if m["id"] != "kaplan_meier"),
        "status_txt": {"acima": "acima da", "abaixo": "abaixo da", "indistinguivel": "estatisticamente igual à"},
    }
    return d


def contexto(res: dict) -> dict:
    return {**res, "d": derivar(res)}


def renderizar(nome_template: str, res: dict, extra: dict | None = None, pasta: Path = C.TEMPLATES_DIR) -> str:
    env = ambiente(pasta)
    ctx = contexto(res)
    if extra:
        ctx.update(extra)
    return env.get_template(nome_template).render(**ctx)


# ------------------------------------------------------------------------------------
# Verificação: templates sem números digitados à mão
# ------------------------------------------------------------------------------------

_PADRAO_NUMERO = re.compile(r"(R\$\s*\d|\d+[.,]\d+|\d+\s*%|\b\d{3,}\b)")
_PERMITIDOS = [
    re.compile(r"\b(?:19|20)\d{2}\b"),                      # anos
    re.compile(r"\bM(?:3|6|12|18|24)\b"),                   # rótulos M12/M18/M24
    re.compile(r"\bPython\s+3\.\d+(?:\s*[–-]\s*3\.\d+)?"),  # versões de Python
    re.compile(r"\bIC\s*95\s*%"),                            # "IC 95%"
    re.compile(r"\b95\s*%"),                                 # nível do IC
    re.compile(r"\bv?\d+\.\d+\.\d+\b"),                      # x.y.z (versões)
    re.compile(r"\b100\s*%"),                                # "100% sintético"
]


def numeros_digitados(texto: str, html: bool = False) -> list[str]:
    """Lista trechos numéricos 'soltos' (fora de {{ }}/{% %} e, em HTML, fora de style/script)."""
    t = re.sub(r"\{%\s*raw\s*%\}.*?\{%\s*endraw\s*%\}", " ", texto, flags=re.S)
    t = re.sub(r"\{\{.*?\}\}", " ", t, flags=re.S)
    t = re.sub(r"\{%.*?%\}", " ", t, flags=re.S)
    t = re.sub(r"\{#.*?#\}", " ", t, flags=re.S)
    if html:
        t = re.sub(r"<(style|script)[^>]*>.*?</\1>", " ", t, flags=re.S | re.I)
        t = re.sub(r"<[^>]+>", " ", t)  # atributos (href, classes, ids) não são texto lido
    t = re.sub(r"```.*?```", " ", t, flags=re.S)             # blocos de código (comandos)
    t = re.sub(r"`[^`]*`", " ", t)                           # código em linha
    t = re.sub(r"\]\([^)]*\)", "]", t)                       # alvo de links markdown
    for permitido in _PERMITIDOS:
        t = permitido.sub(" ", t)
    achados = []
    for m in _PADRAO_NUMERO.finditer(t):
        achados.append(" ".join(t[max(0, m.start() - 15): m.end() + 15].split()))
    return achados
