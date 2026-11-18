"""Figuras (PNG) no estilo editorial 'Gazeta Meridiano'. Tudo vem de df/results.json."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.ticker import FuncFormatter, NullFormatter  # noqa: E402

from . import config as C  # noqa: E402
from . import km as K  # noqa: E402
from . import value as V  # noqa: E402
from .simulate import SAFRAS, rotulo_safra  # noqa: E402

PAPEL = "#FBF8F0"
TINTA = C.COR["tinta"]
MUDO = "#5B5648"
GRADE = "#D9D2BD"
AZUL, VERM, VERDE, OURO = C.COR["meridiano"], C.COR["vermelho"], C.COR["verde"], C.COR["ouro"]


def _estilo() -> None:
    plt.rcParams.update({
        "figure.facecolor": PAPEL, "axes.facecolor": PAPEL, "savefig.facecolor": PAPEL,
        "axes.edgecolor": TINTA, "axes.labelcolor": TINTA, "text.color": TINTA,
        "xtick.color": MUDO, "ytick.color": MUDO, "axes.grid": True, "grid.color": GRADE,
        "grid.linewidth": 0.6, "axes.spines.top": False, "axes.spines.right": False,
        "font.family": "serif", "font.serif": ["DejaVu Serif", "Georgia", "Times New Roman"],
        "font.size": 10, "axes.titlesize": 11.5, "axes.titleweight": "bold",
        "axes.titlelocation": "left", "legend.frameon": False, "legend.fontsize": 8.8,
    })


def _pct_fmt(dec: int = 0):
    return FuncFormatter(lambda v, _: f"{v * 100:.{dec}f}%".replace(".", ","))


def _num(x: float, d: int = 1) -> str:
    return f"{x:.{d}f}".replace(".", ",")


def _salvar(fig, pasta: Path, nome: str) -> Path:
    pasta.mkdir(parents=True, exist_ok=True)
    p = pasta / nome
    fig.savefig(p, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return p


def _ic_curva(km: K.KM, z: float = C.Z95):
    S, g = km.S, km.g
    with np.errstate(divide="ignore", invalid="ignore"):
        se = np.sqrt(g) / np.abs(np.log(S))
        lo, hi = S ** np.exp(z * se), S ** np.exp(-z * se)
    lo = np.where(np.isfinite(lo), lo, S)
    hi = np.where(np.isfinite(hi), hi, S)
    return lo, hi


def _curva_km(ax, sub: pd.DataFrame, cor: str, rotulo: str, t_max: float = 24.0, ic: bool = True):
    km = K.km_curve(sub["duracao_meses"], sub["evento"])
    # corta a cauda onde quase ninguém está sob risco
    ok = np.array([km.em_risco(t) >= C.MIN_EM_RISCO for t in km.t])
    t = np.concatenate([[0.0], km.t[ok]])
    s = np.concatenate([[1.0], km.S[ok]])
    ax.step(t, s, where="post", color=cor, lw=1.9, label=rotulo)
    if ic:
        lo, hi = _ic_curva(km)
        ax.fill_between(np.concatenate([[0.0], km.t[ok]]), np.concatenate([[1.0], lo[ok]]),
                        np.concatenate([[1.0], hi[ok]]), step="post", color=cor, alpha=0.12, lw=0)


def _linhas_meta(ax):
    for h in C.HORIZONTES:
        ax.axvline(h, color=MUDO, lw=0.8, ls=":")
        ax.plot([h - 0.5, h + 0.5], [C.METAS[h]] * 2, color=VERM, lw=2.4, solid_capstyle="butt")
        ax.text(h, 0.09, f"M{h}", ha="center", color=MUDO, fontsize=8.5)


# ------------------------------------------------------------------------------------
def fig_ingenua_vs_km(res: dict, pasta: Path) -> Path:
    tab = res["ingenuo_vs_km"]["safras"]
    fig, (a, b) = plt.subplots(1, 2, figsize=(11.5, 4.1), gridspec_kw={"width_ratios": [1, 1.25]})
    x = np.arange(len(tab))
    a.bar(x, [l["ret_ingenua"] for l in tab], color=OURO, alpha=0.9)
    for i, l in enumerate(tab):
        a.text(i, l["ret_ingenua"] + 0.015, f"{l['ret_ingenua'] * 100:.0f}%".replace(".", ","), ha="center", fontsize=8.5)
    a.set_xticks(x, [l["safra"] for l in tab])
    a.set_ylim(0, 1.08)
    a.yaxis.set_major_formatter(_pct_fmt())
    a.set_title("Ingênuo: ativos ÷ iniciados")
    a.set_xlabel("Safra (trimestre de entrada), da mais antiga à mais recente")
    b.set_title("Kaplan-Meier no mesmo horizonte")
    for h, cor, mk in ((3, AZUL, "o"), (6, VERDE, "s"), (12, VERM, "D"), (18, OURO, "^"), (24, "#6B4E8C", "v")):
        pts = [(i, l["horizontes"][f"m{h}"]) for i, l in enumerate(tab) if l["horizontes"][f"m{h}"]["ok"]]
        xs = [p[0] for p in pts]
        ys = [p[1]["valor"] for p in pts]
        b.plot(xs, ys, color=cor, marker=mk, lw=1.6, label=f"M{h}")
        b.errorbar(xs, ys, yerr=[[p[1]["valor"] - p[1]["lo"] for p in pts], [p[1]["hi"] - p[1]["valor"] for p in pts]],
                   fmt="none", ecolor=cor, elinewidth=1, capsize=2.5, alpha=0.7)
    b.axhline(C.METAS[12], color=VERM, lw=0.9, ls="--")
    b.text(len(tab) - 0.55, C.METAS[12] + 0.008, "meta M12", color=VERM, fontsize=8, ha="right")
    b.set_xticks(x, [l["safra"] for l in tab])
    b.set_ylim(0.3, 1.0)
    b.yaxis.set_major_formatter(_pct_fmt())
    b.set_xlabel("Safra — pontos ausentes = safra sem tempo de observação")
    b.legend(loc="lower left", ncol=5)
    return _salvar(fig, pasta, "01_ingenua_vs_km.png")


def fig_km_grupos(df: pd.DataFrame, coluna: str, ordem, rotulos: dict, cores: dict, titulo: str,
                  pasta: Path, nome: str) -> Path:
    fig, ax = plt.subplots(figsize=(9.2, 5.2))
    for g in ordem:
        _curva_km(ax, df[df[coluna] == g], cores[g], rotulos[g])
    _linhas_meta(ax)
    ax.set_xlim(0, 24)
    ax.set_ylim(0, 1.02)
    ax.set_xlabel("Meses desde o início da assinatura")
    ax.set_ylabel("Probabilidade de seguir assinante")
    ax.yaxis.set_major_formatter(_pct_fmt())
    ax.set_title(titulo)
    ax.legend(loc="upper right", ncol=2)
    ax.text(0.01, 0.02, "Faixas = IC 95% (log-log). Traço vermelho = meta fictícia. Cauda cortada onde há < "
            f"{C.MIN_EM_RISCO} assinantes sob risco.", transform=ax.transAxes, fontsize=7.6, color=MUDO)
    return _salvar(fig, pasta, nome)


def fig_penhasco(df: pd.DataFrame, pasta: Path) -> Path:
    na = df[df["plano"] != "anual"]
    bf = na[na["oferta_entrada"] == "black_friday"]
    ref = na[na["oferta_entrada"] == "nenhuma"]
    fig, ax = plt.subplots(figsize=(9.2, 4.4))
    for sub, cor, rot in ((ref, AZUL, "Sem promoção"), (bf, VERM, "Entrou na Black Friday (60% off por 3 meses)")):
        h = K.hazard_por_idade(sub["duracao_meses"], sub["evento"], max_idade=12)
        xs = [r["k"] for r in h if r["taxa"] is not None and r["n_risco"] >= C.MIN_EM_RISCO]
        ys = [r["taxa"] for r in h if r["taxa"] is not None and r["n_risco"] >= C.MIN_EM_RISCO]
        ax.step(xs + [xs[-1] + 1], ys + [ys[-1]], where="post", color=cor, lw=2, label=rot)
        ax.plot(np.array(xs) + 0.5, ys, "o", color=cor, ms=4)
    ax.axvspan(3, 4, color=VERM, alpha=0.09)
    ax.text(4.15, ax.get_ylim()[1] * 0.93, "penhasco: 1º mês\na preço cheio", ha="left", va="top", color=VERM, fontsize=8.8)
    ax.set_xlim(0, 12)
    ax.set_xticks(range(0, 13))
    ax.yaxis.set_major_formatter(_pct_fmt())
    ax.set_xlabel("Mês de vida da assinatura")
    ax.set_ylabel("Risco mensal de cancelar (taxa observada)")
    ax.set_title("Onde a retenção quebra: o mês seguinte ao fim da promoção")
    ax.legend(loc="upper right")
    return _salvar(fig, pasta, "04_penhasco.png")


def fig_forest(res: dict, pasta: Path) -> Path:
    linhas = [r for r in res["cox"]["plantado_vs_estimado"] if r["ingenuo"] or r["corrigido"]]
    fig, ax = plt.subplots(figsize=(10.2, 0.42 * len(linhas) + 1.6))
    y = np.arange(len(linhas))[::-1]
    for yi, r in zip(y, linhas):
        for chave, cor, mk, dy, rot in (("ingenuo", "#8A8572", "s", 0.2, "Cox ingênuo"),
                                         ("corrigido", AZUL, "o", 0.0, "Cox corrigido"),
                                         ("complementar", VERDE, "^", -0.2, "Cox s/ anual (plano)")):
            e = r[chave]
            if not e:
                continue
            ax.errorbar(e["hr"], yi + dy, xerr=[[e["hr"] - e["lo"]], [e["hi"] - e["hr"]]], fmt=mk, color=cor,
                        ms=5, capsize=2.5, lw=1.2, label=rot)
        if r["verdade"] is not None:
            ax.plot(r["verdade"], yi, "D", color=VERM, ms=6.5, mfc="none", mew=1.6, label="Plantado")
    ax.axvline(1, color=MUDO, lw=0.9)
    ax.set_xscale("log")
    ax.xaxis.set_minor_formatter(NullFormatter())
    ax.set_xticks([0.5, 0.7, 1, 1.5, 2, 3, 4], ["0,5", "0,7", "1", "1,5", "2", "3", "4"])
    ax.set_yticks(y, [r["rotulo"] for r in linhas])
    h, l = ax.get_legend_handles_labels()
    ax.legend(dict(zip(l, h)).values(), dict(zip(l, h)).keys(), loc="lower right")
    ax.set_xlabel("Razão de risco (HR), escala log — IC 95%")
    ax.set_title("Efeito plantado × estimado")
    return _salvar(fig, pasta, "05_cox_forest.png")


def fig_schoenfeld(res: dict, pasta: Path) -> Path:
    fig, (a, b) = plt.subplots(1, 2, figsize=(11.5, 4.1))
    for ax, chave, titulo in ((a, "efeito_local_bf", "Promoção (Black Friday)"),
                              (b, "efeito_local_anual", "Plano anual (vs mensal)")):
        loc = res["cox"]["ingenuo"][chave]
        xs = np.arange(len(loc))
        ax.bar(xs, [l["hr_local"] for l in loc], color=AZUL, alpha=0.85)
        ax.set_xticks(xs, [f"{l['ini']:.0f}–{'+' if l['fim'] is None else format(l['fim'], '.0f')}" for l in loc])
        ax.set_yscale("log")
        ax.yaxis.set_minor_formatter(NullFormatter())
        ax.axhline(1, color=MUDO, lw=0.8)
        coef = "oferta_bf" if chave.endswith("bf") else "plano_anual"
        hr_u = next(r for r in res["cox"]["ingenuo"]["coefs"] if r["nome"] == coef)["hr"]
        ax.axhline(hr_u, color=VERM, ls="--", lw=1.4)
        ax.text(len(loc) - 0.5, hr_u * 1.08, f"HR único do Cox ingênuo = {_num(hr_u, 2)}", color=VERM, ha="right", fontsize=8.5)
        ax.set_title(titulo)
        ax.set_xlabel("Faixa de idade (meses de vida)")
    a.set_ylabel("HR local (resíduos de Schoenfeld escalados)")
    a.set_yticks([0.5, 1, 2, 4], ["0,5", "1", "2", "4"])
    b.set_yticks([0.1, 0.3, 1, 3, 10], ["0,1", "0,3", "1", "3", "10"])
    return _salvar(fig, pasta, "06_schoenfeld.png")


def fig_valor(res: dict, pasta: Path) -> Path:
    can = res["valor"]["canais"]
    ordem = sorted(can, key=lambda c: (not c["escalavel"], -c["ltv_cac"]["est"]))
    fig, (a, b) = plt.subplots(1, 2, figsize=(11.5, 4.3))
    x = np.arange(len(ordem))
    cores = [C.COR_CANAL[c["canal"]] for c in ordem]
    a.bar(x, [c["rmst"]["est"] for c in ordem], color=cores, alpha=0.9,
          yerr=[[c["rmst"]["est"] - c["rmst"]["lo"] for c in ordem], [c["rmst"]["hi"] - c["rmst"]["est"] for c in ordem]],
          capsize=3, ecolor=TINTA)
    a.set_xticks(x, [c["rotulo"].replace(" (Meta)", "") for c in ordem], rotation=20, ha="right")
    a.set_ylabel("Meses esperados de assinatura em 24 meses (RMST)")
    a.set_title("Permanência: tempo médio restrito (RMST 24m)")
    med = np.array([c["ltv_medido"]["est"] for c in ordem])
    prj = np.array([c["ltv_proj"]["est"] for c in ordem])
    b.bar(x, med, color=cores, alpha=0.9, label="LTV medido (KM)")
    b.bar(x, prj, bottom=med, color=cores, alpha=0.45, hatch="//", label="LTV projetado (cauda)")
    b.errorbar(x, [c["ltv"]["est"] for c in ordem], yerr=[[c["ltv"]["est"] - c["ltv"]["lo"] for c in ordem],
                                                          [c["ltv"]["hi"] - c["ltv"]["est"] for c in ordem]],
               fmt="none", ecolor=TINTA, capsize=3)
    b.scatter(x, [c["cac"] for c in ordem], marker="_", s=900, color=TINTA, zorder=4, label="CAC (premissa)")
    for i, c in enumerate(ordem):
        b.text(i, c["ltv"]["hi"] + 12, f"{_num(c['ltv_cac']['est'], 1)}×" if c["escalavel"] else "n/c", ha="center",
               fontsize=8.5, fontweight="bold" if c["escalavel"] else "normal", color=TINTA if c["escalavel"] else MUDO)
    b.set_xticks(x, [c["rotulo"].replace(" (Meta)", "") for c in ordem], rotation=20, ha="right")
    b.set_ylabel("R$ por assinante adquirido")
    b.set_title("LTV de contribuição em 24 meses vs CAC (× = LTV/CAC; canais próprios: n/c)")
    b.set_ylim(0, max(c["ltv"]["hi"] for c in ordem) * 1.32)
    b.legend(loc="upper center", ncol=3, bbox_to_anchor=(0.5, 1.0), fontsize=8)
    return _salvar(fig, pasta, "07_valor_canal.png")


def fig_payback(res: dict, pasta: Path) -> Path:
    fig, ax = plt.subplots(figsize=(9.2, 4.6))
    for c in res["valor"]["canais"]:
        k = c["canal"]
        acum = res["valor"]["curvas"][k]["acum"]
        m = np.arange(1, len(acum) + 1)
        ax.plot(m, acum, color=C.COR_CANAL[k], lw=1.9, label=c["rotulo"])
        ax.axhline(c["cac"], color=C.COR_CANAL[k], lw=0.7, ls=":")
        if c["payback"]["est"] <= C.HORIZONTE_LTV:
            p = int(c["payback"]["est"])
            ax.plot(p, acum[p - 1], "o", color=C.COR_CANAL[k], ms=6)
    ax.set_xlim(1, C.HORIZONTE_LTV)
    ax.set_xlabel("Mensalidades desde a aquisição")
    ax.set_ylabel("Contribuição descontada acumulada esperada (R$)")
    ax.set_title("Payback: quando a contribuição esperada cobre o CAC (linha pontilhada)")
    ax.legend(loc="upper left", ncol=2)
    return _salvar(fig, pasta, "08_payback.png")


def fig_armadilhas(res: dict, pasta: Path) -> Path:
    arm = res["armadilhas"]
    fig, (a, b, c) = plt.subplots(1, 3, figsize=(13.2, 4.2))
    cen = arm["censura"]
    nomes = ["Ativos ÷\niniciados", "Censura =\ncancelou", "Descartar\ncensurados", "Kaplan-\nMeier"]
    vals = [m["valor"] for m in cen["metodos"]]
    a.bar(range(4), vals, color=[OURO, OURO, OURO, AZUL])
    a.axhline(cen["verdade"], color=VERM, lw=1.6, ls="--")
    a.text(1.5, cen["verdade"] + 0.025, "verdade (modelo gerador)", color=VERM, ha="center", fontsize=8.5)
    for i, v in enumerate(vals):
        a.text(i, v + 0.015, f"{v * 100:.0f}%".replace(".", ","), ha="center", fontsize=8.5)
    a.set_xticks(range(4), nomes, fontsize=8)
    a.yaxis.set_major_formatter(_pct_fmt())
    a.set_ylim(0, 0.95)
    a.set_title("(a) M12 ignorando a censura", fontsize=10.5)
    p = arm["riscos_proporcionais"]
    b.bar([0, 1, 2], [p["q_base_mes3"], p["q_previsto_ingenuo"], p["q_previsto_corrigido"]],
          color=["#8A8572", "#8A8572", AZUL])
    b.axhline(p["q_observado_bf_mes3"], color=VERM, lw=1.6, ls="--")
    b.text(-0.45, p["q_observado_bf_mes3"] + 0.003, "observado (BF)", color=VERM, ha="left", fontsize=8.5)
    b.set_ylim(0, p["q_observado_bf_mes3"] * 1.25)
    for i, v in enumerate([p["q_base_mes3"], p["q_previsto_ingenuo"], p["q_previsto_corrigido"]]):
        b.text(i, v + 0.004, f"{v * 100:.1f}%".replace(".", ","), ha="center", fontsize=8.5)
    b.set_xticks([0, 1, 2], ["Sem promoção\n(base)", "Previsto:\nCox ingênuo", "Previsto:\nCox corrigido"], fontsize=8)
    b.yaxis.set_major_formatter(_pct_fmt())
    b.set_title("(b) Cancelar no mês 3–4", fontsize=10.5)
    r = arm["ranking"]
    c.bar([0, 1], [r["p_acerta_melhor"], r["p_acerta_pior"]], color=[VERDE, VERM], alpha=0.9)
    for i, v in enumerate([r["p_acerta_melhor"], r["p_acerta_pior"]]):
        c.text(i, v + 0.02, f"{v * 100:.0f}%".replace(".", ","), ha="center", fontsize=9, fontweight="bold")
    c.axhline(1 / len(C.CANAIS), color=MUDO, ls=":", lw=1)
    c.text(0.5, 1 / len(C.CANAIS) + 0.015, "acaso", color=MUDO, ha="center", fontsize=8.5)
    c.set_xticks([0, 1], ["acerta o MELHOR\ncanal", "acerta o PIOR\ncanal"], fontsize=8)
    c.yaxis.set_major_formatter(_pct_fmt())
    c.set_ylim(0, 1.05)
    c.set_title(f"(c) Ranking bruto, n={r['tamanho_safra_pequena']}", fontsize=10.5)
    return _salvar(fig, pasta, "09_armadilhas.png")


def fig_riscos_competitivos(res: dict, pasta: Path) -> Path:
    rc = res["riscos_competitivos"]
    fig, (a, b) = plt.subplots(1, 2, figsize=(11.5, 4.2), gridspec_kw={"width_ratios": [1.3, 1]})
    cores = {"voluntario": AZUL, "involuntario": OURO, "fim_contrato": VERM}
    g = rc["grade"]
    base = np.zeros(len(g))
    for k in C.CAUSAS:
        y = np.array(rc["curvas"][k])
        a.fill_between(g, base, base + y, color=cores[k], alpha=0.85, step="post", label=C.CAUSAS_ROTULO[k], lw=0)
        base = base + y
    a.plot(g, rc["curva_total"], color=TINTA, lw=1, ls="--", label="1 − KM (todas as causas)")
    a.set_xlim(0, 24)
    a.yaxis.set_major_formatter(_pct_fmt())
    a.set_xlabel("Meses desde o início")
    a.set_ylabel("Incidência acumulada (Aalen-Johansen)")
    a.set_title("Quem sai, e por quê")
    a.legend(loc="upper left")
    pl = rc["por_plano"]
    xs = np.arange(len(C.PLANOS))
    fundo = np.zeros(len(C.PLANOS))
    for k in C.CAUSAS:
        y = np.array([pl[p]["cif_m13"][k] for p in C.PLANOS])
        b.bar(xs, y, bottom=fundo, color=cores[k], alpha=0.9)
        fundo += y
    b.set_xticks(xs, [C.PLANOS_ROTULO[p].replace(" Streaming", "") for p in C.PLANOS])
    b.yaxis.set_major_formatter(_pct_fmt())
    b.set_title("Por plano, até o mês 13")
    return _salvar(fig, pasta, "10_riscos_competitivos.png")


def fig_decisao(res: dict, pasta: Path) -> Path:
    fig, (a, b) = plt.subplots(1, 2, figsize=(11.5, 4.1))
    esc = [c for c in res["valor"]["canais"] if c["escalavel"]]
    esc = sorted(esc, key=lambda c: C.CAC[c["canal"]])
    x = np.arange(len(esc))
    w = 0.38
    a.bar(x - w / 2, [1 / C.CAC[c["canal"]] * 100 for c in esc], w, color=OURO, label="Assinantes por R$ 100 (só CAC)")
    a.bar(x + w / 2, [c["ltv_cac"]["est"] for c in esc], w, color=AZUL, label="Retorno por R$ 1 (LTV/CAC)")
    a.set_xticks(x, [c["rotulo"].replace(" (Meta)", "") for c in esc])
    a.set_title("Canais com verba: só CAC × permanência")
    a.legend(loc="upper right")
    cen = res["acao_mes3"]["projetado"]["cenarios"]
    b.bar([f"{c['efetividade'] * 100:.0f}%" for c in cen], [c["liquido"] for c in cen],
          color=[VERDE if c["liquido"] > 0 else VERM for c in cen])
    b.axhline(0, color=TINTA, lw=0.8)
    for i, c in enumerate(cen):
        b.text(i, c["liquido"] + (200 if c["liquido"] >= 0 else -200), f"R$ {c['liquido']:,.0f}".replace(",", "."),
               ha="center", va="bottom" if c["liquido"] >= 0 else "top", fontsize=8.8)
    b.set_xlabel("Efetividade assumida da ação (% do excesso de cancelamentos evitado)")
    b.set_ylabel("Líquido projetado (R$)")
    b.set_title("Ação no mês 3: projeção, não medição")
    return _salvar(fig, pasta, "11_decisao.png")


# ------------------------------------------------------------------------------------
# Figuras novas: realocação por cenário, operação (MRR), fora do tempo e dataset público
# ------------------------------------------------------------------------------------

def fig_realocacao(res: dict, pasta: Path) -> Path:
    r = res["decisao_verba"]["realocacao"]["pior_para_melhor"]
    ro, rd = C.CANAIS_ROTULO[r["origem"]], C.CANAIS_ROTULO[r["destino"]]
    fig, (a, b) = plt.subplots(1, 2, figsize=(11.5, 4.2), gridspec_kw={"width_ratios": [1.25, 1]})
    lin = r["linhas"]
    x = np.arange(len(lin))
    ganho = np.array([l["ganho"] for l in lin]) / 1e3
    lo = np.array([l["lo"] for l in lin]) / 1e3
    hi = np.array([l["hi"] for l in lin]) / 1e3
    a.bar(x, ganho, color=[VERDE if g > 0 else VERM for g in ganho], alpha=0.9)
    a.errorbar(x, ganho, yerr=[ganho - lo, hi - ganho], fmt="none", ecolor=TINTA, capsize=4, lw=1.3)
    a.axhline(0, color=TINTA, lw=0.8)
    a.set_xticks(x, [f"+{l['premio'] * 100:.0f}%" if l["premio"] > 0 else "igual ao médio" for l in lin])
    a.set_xlabel(f"CAC marginal de {rd} acima do médio")
    a.set_ylabel("Valor líquido projetado (R$ mil)")
    a.set_title(f"Mover R$ {C.VERBA_EXEMPLO / 1e3:.0f} mil de {ro} para {rd}")
    a.text(0.01, 0.02, "Barras = estimativa; traço = IC 95% (bootstrap + CAC ±30%)", transform=a.transAxes,
           fontsize=7.8, color=MUDO)
    esc = [c for c in res["valor"]["canais"] if c["escalavel"]]
    esc = sorted(esc, key=lambda c: -c["ltv_cac_incerteza"]["est"])
    y = np.arange(len(esc))
    est = np.array([c["ltv_cac_incerteza"]["est"] for c in esc])
    l2 = np.array([c["ltv_cac_incerteza"]["lo"] for c in esc])
    h2 = np.array([c["ltv_cac_incerteza"]["hi"] for c in esc])
    b.barh(y, est, color=[C.COR_CANAL[c["canal"]] for c in esc], alpha=0.9)
    b.errorbar(est, y, xerr=[est - l2, h2 - est], fmt="none", ecolor=TINTA, capsize=3, lw=1.2)
    for i, c in enumerate(esc):
        b.text(h2[i] + 0.15, i, f"{c['prob_melhor_ltv_cac'] * 100:.0f}% melhor", va="center", fontsize=8.2)
    b.set_yticks(y, [c["rotulo"].replace(" (Meta)", "") for c in esc])
    b.invert_yaxis()
    b.set_xlabel("LTV de contribuição ÷ CAC")
    b.set_xlim(0, float(h2.max()) * 1.35)
    b.set_title("Retorno por real, com CAC incerto (±30%)")
    return _salvar(fig, pasta, "12_realocacao.png")


def fig_mrr(res: dict, pasta: Path) -> Path:
    op = res["operacao"]
    pt = op["ponte"][1:]
    fig, (a, b) = plt.subplots(1, 2, figsize=(12.4, 4.4), gridspec_kw={"width_ratios": [1.6, 1]})
    x = np.arange(len(pt))
    pos = [("novo", AZUL, "Novos"), ("reativacao", "#3D8FA3", "Reativações"), ("exp_upgrade", VERDE, "Upgrade de plano"),
           ("exp_fim_promo", "#7BA987", "Fim da promoção"), ("exp_reajuste", OURO, "Reajuste de preço")]
    base = np.zeros(len(pt))
    for k, cor, rot in pos:
        v = np.array([p[k] for p in pt]) / 1e3
        a.bar(x, v, bottom=base, color=cor, label=rot, width=0.8)
        base += v
    neg = [("churn", VERM, "Churn"), ("contracao", "#C98A8A", "Downgrade")]
    fundo = np.zeros(len(pt))
    for k, cor, rot in neg:
        v = np.array([p[k] for p in pt]) / 1e3
        a.bar(x, v, bottom=fundo, color=cor, label=rot, width=0.8)
        fundo += v
    a.axhline(0, color=TINTA, lw=0.8)
    a.set_xticks(x[::3], [p["mes"][2:] for p in pt][::3], fontsize=8, rotation=0)
    a.set_ylabel("R$ mil de MRR no mês")
    a.set_title("Ponte de MRR: o que entra e o que sai a cada mês")
    fim = np.array([p["final"] for p in pt])
    topo = max(float(base.max()), 1.0)
    escala = topo * 0.92 / float(fim.max())
    a.plot(x, fim * escala, color=TINTA, lw=1.6, label="MRR no fim do mês (fora de escala)")
    a.legend(loc="upper left", ncol=2, fontsize=7.6)
    rr = op["retencao_receita"]
    rot = ["Base toda"] + [C.CANAIS_ROTULO[c].replace(" (Meta)", "") for c in C.CANAIS]
    vals = [rr["global"]] + [rr["por_canal"][c] for c in C.CANAIS]
    y = np.arange(len(vals))
    nrr = np.array([v["nrr"] for v in vals])
    b.barh(y, nrr, color=[TINTA] + [C.COR_CANAL[c] for c in C.CANAIS], alpha=0.9)
    b.errorbar(nrr, y, xerr=[nrr - np.array([v["nrr_lo"] for v in vals]), np.array([v["nrr_hi"] for v in vals]) - nrr],
               fmt="none", ecolor=TINTA, capsize=3, lw=1.1)
    b.plot([v["grr"] for v in vals], y, "D", color=VERM, ms=5, label="GRR (sem expansão)")
    b.axvline(1.0, color=MUDO, ls=":", lw=1)
    b.set_yticks(y, rot)
    b.invert_yaxis()
    b.xaxis.set_major_formatter(_pct_fmt())
    b.set_xlim(0.4, 1.05)
    b.set_title(f"Retenção líquida de receita em {C.JANELA_NRR_MESES} meses (NRR)")
    b.legend(loc="lower left", fontsize=8)
    return _salvar(fig, pasta, "13_mrr.png")


def fig_fora_do_tempo(res: dict, pasta: Path) -> Path:
    f = res["preditivo"]["fora_do_tempo"]
    fig, (a, b) = plt.subplots(1, 2, figsize=(11.2, 4.2), gridspec_kw={"width_ratios": [1.25, 1]})
    cal = [c for c in f["calibracao"] if c["observado"] is not None]
    prev = np.array([c["previsto"] for c in cal])
    obs = np.array([c["observado"] for c in cal])
    lo = np.array([c["lo"] for c in cal])
    hi = np.array([c["hi"] for c in cal])
    m = max(float(hi.max()), float(prev.max())) * 1.08
    a.plot([0, m], [0, m], color=MUDO, ls="--", lw=1)
    a.errorbar(prev, obs, yerr=[obs - lo, hi - obs], fmt="o", color=AZUL, ecolor=AZUL, capsize=3, ms=6)
    for c in cal:
        a.text(c["previsto"] + 0.006, c["observado"] - 0.001, f"Q{c['faixa']}", fontsize=8, ha="left", va="top", color=MUDO)
    a.set_xlim(0, m)
    a.set_ylim(0, m)
    a.xaxis.set_major_formatter(_pct_fmt())
    a.yaxis.set_major_formatter(_pct_fmt())
    a.set_xlabel(f"Prob. de cancelar em {f['horizonte']} meses PREVISTA (modelo treinado até {f['t0'][8:10]}/{f['t0'][5:7]}/{f['t0'][:4]})")
    a.set_ylabel("Observada (Kaplan-Meier, quem entrou depois)")
    a.set_title("Calibração fora do tempo, por quintil de risco")
    ci = f["cindex"]
    nomes = ["Treino\n(até T0)", "Teste\n(depois de T0)", "Teto: risco\nverdadeiro"]
    v = [ci["treino"], ci["teste"], ci["teto_verdadeiro"]]
    b.bar(range(3), v, color=[OURO, AZUL, VERDE], alpha=0.9)
    for i, x in enumerate(v):
        b.text(i, x + 0.006, _num(x, 3), ha="center", fontsize=9, fontweight="bold")
    b.axhline(0.5, color=MUDO, ls=":", lw=1)
    b.set_ylim(0.45, max(v) * 1.08)
    b.yaxis.set_major_formatter(FuncFormatter(lambda y, _: f"{y:.2f}".replace(".", ",")))
    b.set_xticks(range(3), nomes, fontsize=8.5)
    b.set_title(f"C-index ({f['horizonte']} meses; pontilhado = acaso)")
    return _salvar(fig, pasta, "14_fora_do_tempo.png")


def fig_externo(res: dict, pasta: Path) -> Path:
    from . import externo as E
    ex = res["externo"]
    d = E.carregar()
    cores = {"Month-to-month": VERM, "One year": OURO, "Two year": VERDE}
    fig, (a, b) = plt.subplots(1, 2, figsize=(11.4, 4.2))
    for c in E.CONTRATOS:
        s = d[d["Contract"] == c]
        km = K.km_curve(s["duracao"], s["evento"])
        ok = np.array([km.em_risco(t) >= C.MIN_EM_RISCO for t in km.t])
        t = np.concatenate([[0.0], km.t[ok]])
        y = np.concatenate([[1.0], km.S[ok]])
        a.step(t, y, where="post", color=cores[c], lw=1.9, label=E.ROT_CONTRATO[c])
        lo, hi = _ic_curva(km)
        a.fill_between(t, np.concatenate([[1.0], lo[ok]]), np.concatenate([[1.0], hi[ok]]), step="post",
                       color=cores[c], alpha=0.12, lw=0)
    a.set_xlabel("Meses de contrato (tenure)")
    a.set_ylabel("Probabilidade de seguir cliente")
    a.yaxis.set_major_formatter(_pct_fmt())
    a.set_ylim(0, 1.02)
    a.set_title("Dataset público: KM por tipo de contrato", fontsize=10.5)
    a.legend(loc="lower left")
    faixas = ex["taxa_por_faixa"]
    xs = np.arange(len(faixas))
    for c in E.CONTRATOS:
        y = [f[c] if f[c] and f[c] > 0 else np.nan for f in faixas]
        b.plot(xs, y, marker="o", color=cores[c], lw=1.7, label=E.ROT_CONTRATO[c])
    b.set_yscale("log")
    b.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v * 100:g}%".replace(".", ",")))
    b.yaxis.set_minor_formatter(NullFormatter())
    rotulos = []
    for f in faixas:
        rotulos.append("1º mês" if (f["ini"], f["fim"]) == (0, 1) else
                       f"{f['ini'] + 1}–{f['fim']}" if f["fim"] < 73 else f"{f['ini'] + 1}+")
    b.set_xticks(xs, rotulos, fontsize=8)
    b.set_xlabel("Meses de contrato")
    b.set_ylabel("Cancelamentos por mês (escala log)")
    b.set_title("O risco não é proporcional entre contratos", fontsize=10.5)
    return _salvar(fig, pasta, "15_dataset_publico.png")


def gerar_todas(df: pd.DataFrame, res: dict, pasta: Path = C.FIGURES_DIR) -> dict[str, Path]:
    _estilo()
    saidas = {}
    saidas["ingenua_vs_km"] = fig_ingenua_vs_km(res, pasta)
    saidas["km_canal"] = fig_km_grupos(df, "canal", C.CANAIS, C.CANAIS_ROTULO, C.COR_CANAL,
                                       "Sobrevivência por canal de aquisição", pasta, "02_km_canal.png")
    saidas["km_plano"] = fig_km_grupos(df, "plano", C.PLANOS, C.PLANOS_ROTULO, C.COR_PLANO,
                                       "Sobrevivência por plano: o anual cai na renovação", pasta, "03_km_plano.png")
    saidas["penhasco"] = fig_penhasco(df, pasta)
    saidas["forest"] = fig_forest(res, pasta)
    saidas["schoenfeld"] = fig_schoenfeld(res, pasta)
    saidas["valor"] = fig_valor(res, pasta)
    saidas["payback"] = fig_payback(res, pasta)
    saidas["armadilhas"] = fig_armadilhas(res, pasta)
    if "riscos_competitivos" in res:
        saidas["riscos_competitivos"] = fig_riscos_competitivos(res, pasta)
    saidas["decisao"] = fig_decisao(res, pasta)
    saidas["realocacao"] = fig_realocacao(res, pasta)
    saidas["mrr"] = fig_mrr(res, pasta)
    saidas["fora_do_tempo"] = fig_fora_do_tempo(res, pasta)
    saidas["externo"] = fig_externo(res, pasta)
    return saidas
