"""Gerador determinístico de assinantes sintéticos (modelo de risco por partes).

Cada assinante tem uma duração LATENTE T gerada por um modelo exponencial por intervalos
(risco constante por dia dentro de cada mês de vida, com efeitos de canal, plano, engajamento,
oferta de entrada e calendário). Depois aplicamos a censura à direita no corte de observação.

Ordem aleatória fixa via ``SeedSequence(SEED).spawn``: a mesma seed gera sempre os mesmos dados.
A VERDADE do processo (HRs plantados, sobrevivência verdadeira) é gravada em ground_truth.json.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
import pandas as pd

from . import config as C


@dataclass
class Latente:
    """Quantidades latentes (não observáveis na vida real) usadas só para validar o método."""

    t_latente: np.ndarray        # duração latente em meses (sem corte), inf se além da grade
    causa_latente: np.ndarray    # causa do cancelamento latente
    s_true_mes: np.ndarray       # (n, 25): S_i(t) verdadeira em t = 0..24 meses
    taxa_mes_ref: np.ndarray     # (n,) multiplicador de covariáveis (para diagnóstico)


# ------------------------------------------------------------------------------------
# Entradas: datas, canais, planos, dispositivo, engajamento, oferta
# ------------------------------------------------------------------------------------

def _dias_janela() -> pd.DatetimeIndex:
    return pd.date_range(C.ENTRADA_INI, C.ENTRADA_FIM, freq="D")


def _marca_campanhas(dias: pd.DatetimeIndex) -> dict[str, np.ndarray]:
    """Máscaras booleanas por tipo de campanha ao longo dos dias da janela."""
    marcas = {"black_friday": np.zeros(len(dias), bool),
              "passe_copa": np.zeros(len(dias), bool),
              "eleicoes": np.zeros(len(dias), bool)}
    for nome, (ini, fim, _) in C.CAMPANHAS.items():
        if nome.startswith("black_friday"):
            tipo = "black_friday"
        elif nome.startswith("passe_copa"):
            tipo = "passe_copa"
        else:
            tipo = "eleicoes"
        m = (dias >= pd.Timestamp(ini)) & (dias <= pd.Timestamp(fim))
        marcas[tipo] |= np.asarray(m)
    return marcas


def _intensidade_dia(dias: pd.DatetimeIndex) -> np.ndarray:
    meses = (dias - pd.Timestamp(C.ENTRADA_INI)).days.to_numpy() / C.DIAS_POR_MES
    w = (1.0 + C.CRESCIMENTO_MENSAL) ** meses
    for _, (ini, fim, mult) in C.CAMPANHAS.items():
        m = np.asarray((dias >= pd.Timestamp(ini)) & (dias <= pd.Timestamp(fim)))
        w = np.where(m, w * mult, w)
    return w


def _amostra_categorica(rng: np.random.Generator, probs: np.ndarray) -> np.ndarray:
    """Sorteia um índice por linha de ``probs`` (n, k) já normalizado."""
    u = rng.random(len(probs))
    return (probs.cumsum(axis=1) < u[:, None]).sum(axis=1).clip(0, probs.shape[1] - 1)


def gerar_entradas(seed: int = C.SEED, n: int = C.N_ASSINANTES) -> pd.DataFrame:
    ss = np.random.SeedSequence(seed)
    r_data, r_canal, r_plano, r_resto = (np.random.default_rng(s) for s in ss.spawn(4)[:4])

    dias = _dias_janela()
    marcas = _marca_campanhas(dias)
    w = _intensidade_dia(dias)
    idx_dia = r_data.choice(len(dias), size=n, p=w / w.sum())
    idx_dia = np.sort(idx_dia)  # ordem cronológica (ids crescem com a data)

    # canal | dia (campanhas deslocam a composição)
    base = np.array([C.CANAL_PESOS[c] for c in C.CANAIS])
    tilt_dia = np.ones((len(dias), len(C.CANAIS)))
    for tipo, tilt in C.CANAL_TILT_CAMPANHA.items():
        for j, c in enumerate(C.CANAIS):
            if c in tilt:
                tilt_dia[marcas[tipo], j] *= tilt[c]
    pc = base[None, :] * tilt_dia[idx_dia]
    pc /= pc.sum(axis=1, keepdims=True)
    canal_idx = _amostra_categorica(r_canal, pc)
    canal = np.array(C.CANAIS)[canal_idx]

    # plano | canal
    bp = np.array([C.PLANO_PESOS[p] for p in C.PLANOS])
    tilt_c = {c: np.array([C.PLANO_TILT_CANAL.get(c, {}).get(p, 1.0) for p in C.PLANOS])
              for c in C.CANAIS}
    pp = np.vstack([bp * tilt_c[c] for c in canal])
    pp /= pp.sum(axis=1, keepdims=True)
    plano = np.array(C.PLANOS)[_amostra_categorica(r_plano, pp)]

    # dispositivo, engajamento e oferta
    disp = r_resto.choice(C.DISPOSITIVOS, size=n,
                          p=[C.DISPOSITIVO_PESOS[d] for d in C.DISPOSITIVOS])
    desloca = np.array([C.ENG_DESLOCA_CANAL[c] for c in canal])
    eng = np.clip(r_resto.normal(C.ENG_MEDIA + desloca, C.ENG_DP), 0, 100).round(1)

    u_bf = r_resto.random(n)
    u_copa = r_resto.random(n)
    nao_anual = plano != "anual"
    oferta = np.full(n, "nenhuma", dtype=object)
    oferta[marcas["black_friday"][idx_dia] & nao_anual & (u_bf < C.P_OFERTA_BF)] = "black_friday"
    oferta[marcas["passe_copa"][idx_dia] & nao_anual & (u_copa < C.P_OFERTA_COPA)] = "passe_copa"

    datas = dias[idx_dia]
    df = pd.DataFrame({
        "id_assinante": [f"A{i + 1:06d}" for i in range(n)],
        "data_inicio": datas,
        "canal": canal,
        "plano": plano,
        "oferta_entrada": oferta,
        "dispositivo": disp,
        "engajamento_pre": eng,
    })
    return df


def atribuir_safra(datas: pd.Series) -> pd.Series:
    """Safra = bloco de 3 meses contados a partir de ENTRADA_INI (S1 .. S8)."""
    ini = pd.Timestamp(C.ENTRADA_INI)
    meses = (datas.dt.year - ini.year) * 12 + (datas.dt.month - ini.month)
    return ("S" + (meses // C.MESES_POR_SAFRA + 1).astype(int).astype(str)).rename("safra")


_MES_ABREV = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def rotulo_safra(i: int) -> str:
    """Rótulo legível da safra Si (i = 1..8), ex.: 'Nov/24–Jan/25'."""
    ini = pd.Timestamp(C.ENTRADA_INI) + pd.DateOffset(months=(i - 1) * C.MESES_POR_SAFRA)
    fim = ini + pd.DateOffset(months=C.MESES_POR_SAFRA - 1)
    f = lambda t: f"{_MES_ABREV[t.month - 1].capitalize()}/{str(t.year)[2:]}"  # noqa: E731
    return f"{f(ini)}–{f(fim)}"


SAFRAS = tuple(f"S{i}" for i in range(1, C.N_SAFRAS + 1))


# ------------------------------------------------------------------------------------
# Modelo de risco
# ------------------------------------------------------------------------------------

def _forma_tenure(k: np.ndarray) -> np.ndarray:
    out = np.ones(len(k))
    for kk, v in C.FORMA_TENURE.items():
        out[k == kk] = v
    out[k >= 12] = C.TENURE_LONGO
    return out


def multiplicador_covariaveis(df: pd.DataFrame) -> np.ndarray:
    """Multiplicador de risco por assinante (parte proporcional do modelo plantado)."""
    z = (df["engajamento_pre"].to_numpy() - C.ENG_MEDIA) / C.ENG_DP
    m = (df["canal"].map(C.HR_CANAL).to_numpy()
         * df["dispositivo"].map(C.HR_DISPOSITIVO).to_numpy()
         * C.HR_ENGAJ_POR_DP ** z
         * np.where(df["oferta_entrada"] == "passe_copa", C.HR_PASSE_COPA, 1.0))
    hr_plano = df["plano"].map(C.HR_PLANO).fillna(1.0).to_numpy()  # anual: NaN -> 1
    return m * hr_plano


def _taxas_diarias(df: pd.DataFrame, mult: np.ndarray, d0: int, d1: int,
                   n_dias: int, desloc_dias: float = 0.0) -> np.ndarray:
    """Matriz (len, n_dias) de risco por dia de vida para as linhas d0:d1 de ``df``.

    ``desloc_dias`` desloca o efeito por período da promoção (variante de robustez: o penhasco acontece
    meio mês depois do que o modelo corrigido supõe). Zero = o desenho oficial."""
    sub = df.iloc[d0:d1]
    ages = np.arange(n_dias)
    k = np.floor(ages / C.DIAS_POR_MES).astype(int)
    shape = _forma_tenure(k)

    base_nao_anual = C.HAZARD_BASE * shape / C.DIAS_POR_MES
    taxa_anual_k = np.where((k >= C.ANUAL_RENOVACAO_K) & (k % C.ANUAL_RENOVACAO_K == 0),
                            C.ANUAL_TAXA_RENOVACAO, C.HAZARD_BASE * C.ANUAL_HR_PRE)
    base_anual = taxa_anual_k / C.DIAS_POR_MES

    anual = (sub["plano"] == "anual").to_numpy()
    h = np.where(anual[:, None], base_anual[None, :], base_nao_anual[None, :]) \
        * mult[d0:d1, None]

    # promoção Black Friday: efeito por período (viola riscos proporcionais)
    bf = (sub["oferta_entrada"] == "black_friday").to_numpy()
    if bf.any():
        promo_k = np.ones(n_dias)
        k_p = np.floor((ages - desloc_dias) / C.DIAS_POR_MES).astype(int)
        for p in C.HR_PROMO_PERIODOS.values():
            promo_k[(k_p >= p["k_ini"]) & (k_p < p["k_fim"])] = p["hr"]
        h[bf] *= promo_k[None, :]

    # reajuste de preço em Mensal/Combo: efeito de CALENDÁRIO durante a janela
    exp = sub["plano"].isin(C.REAJUSTE_PLANOS).to_numpy()
    if exp.any():
        ini0 = (sub["data_inicio"] - pd.Timestamp(C.ENTRADA_INI)).dt.days.to_numpy()
        r_ini = (pd.Timestamp(C.REAJUSTE_INI) - pd.Timestamp(C.ENTRADA_INI)).days
        r_fim = (pd.Timestamp(C.REAJUSTE_FIM) - pd.Timestamp(C.ENTRADA_INI)).days
        cal = ini0[:, None] + ages[None, :]
        m_r = (cal >= r_ini) & (cal <= r_fim) & exp[:, None]
        h = np.where(m_r, h * C.HR_REAJUSTE, h)
    return h


def simular(seed: int = C.SEED, n: int = C.N_ASSINANTES, fragilidade: float = 0.0,
            desloc_penhasco_dias: float = 0.0) -> tuple[pd.DataFrame, Latente]:
    """Gera o dataset observado (com censura) e as quantidades latentes de verdade.

    Os dois argumentos extras criam VARIANTES de robustez (zero = desenho oficial, que não muda):
    ``fragilidade`` = variância de uma heterogeneidade gama NÃO observada que multiplica o risco de cada assinante;
    ``desloc_penhasco_dias`` = atraso do efeito por período da promoção (o modelo corrigido supõe o mês 3–4)."""
    df = gerar_entradas(seed, n)
    ss = np.random.SeedSequence(seed)
    r_t, r_causa = (np.random.default_rng(s) for s in ss.spawn(6)[4:6])

    mult = multiplicador_covariaveis(df)
    if fragilidade > 0:
        r_frag = np.random.default_rng(np.random.SeedSequence(seed).spawn(11)[10])
        mult = mult * r_frag.gamma(1.0 / fragilidade, fragilidade, size=n)  # média 1, variância = fragilidade
    n_dias = int(np.ceil(C.MESES_LATENTES * C.DIAS_POR_MES))
    E = r_t.standard_exponential(n)

    t_lat = np.full(n, np.inf)
    k_ev = np.zeros(n, dtype=int)
    s_mes = np.ones((n, 25))
    passo = 3000
    for a in range(0, n, passo):
        b = min(a + passo, n)
        h = _taxas_diarias(df, mult, a, b, n_dias, desloc_penhasco_dias)
        H = np.cumsum(h, axis=1)
        e = E[a:b]
        pos = (H < e[:, None]).sum(axis=1)          # primeiro dia em que H >= E
        ok = pos < n_dias
        pos_c = np.minimum(pos, n_dias - 1)
        h_ant = np.where(pos_c > 0, H[np.arange(b - a), np.maximum(pos_c - 1, 0)], 0.0)
        frac = (e - h_ant) / h[np.arange(b - a), pos_c]
        t_dias = pos_c + frac
        t_lat[a:b] = np.where(ok, t_dias / C.DIAS_POR_MES, np.inf)
        k_ev[a:b] = np.where(ok, np.floor(t_dias / C.DIAS_POR_MES), -1).astype(int)
        # sobrevivência verdadeira em t = 0..24 meses (interpola dentro do dia)
        for m in range(1, 25):
            x = m * C.DIAS_POR_MES
            nfull = int(np.floor(x))
            Hm = H[:, nfull - 1] + (x - nfull) * h[:, nfull]
            s_mes[a:b, m] = np.exp(-Hm)

    # causas (atribuídas por sorteio; não alteram o risco total)
    u = r_causa.random(n)
    anual = (df["plano"] == "anual").to_numpy()
    bf = (df["oferta_entrada"] == "black_friday").to_numpy()
    p_inv = np.full(n, C.P_INVOL_BASE)
    p_inv = np.where(k_ev <= 1, C.P_INVOL_INICIO, p_inv)
    p_inv = np.where(bf & (k_ev == 3), C.P_INVOL_PENHASCO, p_inv)
    renov = (k_ev >= C.ANUAL_RENOVACAO_K) & (k_ev % C.ANUAL_RENOVACAO_K == 0)
    p_inv = np.where(anual & renov, C.P_INVOL_RENOVACAO, p_inv)
    p_inv = np.where(anual & ~renov, 0.0, p_inv)  # anual pago adiantado: sem falha antes
    causa = np.where(u < p_inv, "involuntario", "voluntario").astype(object)
    causa = np.where(anual & renov & (u >= p_inv), "fim_contrato", causa)
    causa[~np.isfinite(t_lat)] = ""

    # censura à direita no corte
    dias_pot = (pd.Timestamp(C.CORTE) - df["data_inicio"]).dt.days.to_numpy() + 1
    pot = dias_pot / C.DIAS_POR_MES
    evento = t_lat < pot
    duracao = np.where(evento, t_lat, pot)
    df["safra"] = atribuir_safra(df["data_inicio"])
    df["seguimento_max_meses"] = pot.round(6)
    df["duracao_meses"] = duracao.round(6)
    df["evento"] = evento.astype(int)
    df["causa"] = np.where(evento, causa, "")
    cancel = df["data_inicio"] + pd.to_timedelta(np.where(evento, t_lat * C.DIAS_POR_MES, 0.0), unit="D")
    df["data_cancelamento"] = cancel.dt.normalize().where(evento)
    df["duracao_meses"] = df["duracao_meses"].clip(lower=1e-6)

    lat = Latente(t_latente=t_lat, causa_latente=causa, s_true_mes=s_mes, taxa_mes_ref=mult)
    return df, lat


# ------------------------------------------------------------------------------------
# Verdade (ground truth)
# ------------------------------------------------------------------------------------

def _s_media(s_mes: np.ndarray, mask: np.ndarray, h: int) -> float | None:
    if mask.sum() < C.MIN_EM_RISCO:
        return None
    return float(s_mes[mask, h].mean())


def construir_ground_truth(df: pd.DataFrame, lat: Latente) -> dict:
    pot = df["seguimento_max_meses"].to_numpy()
    grupos = {"canal": df["canal"].to_numpy(), "plano": df["plano"].to_numpy(),
              "safra": df["safra"].to_numpy()}
    sv: dict = {"global": {}, "por_canal": {}, "por_plano": {}, "por_safra": {}}
    for h in C.HORIZONTES:
        elig = pot >= h
        sv["global"][f"m{h}"] = {
            "todos": float(lat.s_true_mes[:, h].mean()),
            "elegiveis": _s_media(lat.s_true_mes, elig, h),
            "n_elegiveis": int(elig.sum()),
        }
        for nome, chave in (("por_canal", "canal"), ("por_plano", "plano"), ("por_safra", "safra")):
            for g in np.unique(grupos[chave]):
                sel = grupos[chave] == g
                sv[nome].setdefault(g, {})[f"m{h}"] = {
                    "todos": float(lat.s_true_mes[sel, h].mean()),
                    "elegiveis": _s_media(lat.s_true_mes, sel & elig, h),
                }
    # CIF verdadeira aos 12 meses por causa (entre elegíveis)
    elig12 = pot >= 12
    cif = {}
    for c in C.CAUSAS:
        cif[c] = float(((lat.causa_latente == c) & (lat.t_latente <= 12) & elig12)[elig12].mean())
    return {
        "descricao": "Verdade do processo gerador (dados sintéticos). HRs são multiplicativos "
                     "sobre o risco mensal-base.",
        "seed": C.SEED,
        "n": int(len(df)),
        "risco_mensal_base": C.HAZARD_BASE,
        "hr": {
            "canal": {c: C.HR_CANAL[c] for c in C.CANAIS if c != C.CANAL_REF},
            "plano_nao_anual": {p: C.HR_PLANO[p] for p in C.HR_PLANO if p != C.PLANO_REF},
            "dispositivo": {d: C.HR_DISPOSITIVO[d] for d in C.DISPOSITIVOS if d != C.DISPOSITIVO_REF},
            "engajamento_por_dp": C.HR_ENGAJ_POR_DP,
            "passe_copa": C.HR_PASSE_COPA,
            "reajuste_mensal_combo": C.HR_REAJUSTE,
            "promo_periodos": {k: v["hr"] for k, v in C.HR_PROMO_PERIODOS.items()},
        },
        "anual": {"hr_pre_renovacao": C.ANUAL_HR_PRE,
                  "taxa_mensal_na_renovacao": C.ANUAL_TAXA_RENOVACAO,
                  "mes_renovacao": C.ANUAL_RENOVACAO_K},
        "causas": {"p_invol_base": C.P_INVOL_BASE, "p_invol_inicio": C.P_INVOL_INICIO,
                   "p_invol_penhasco": C.P_INVOL_PENHASCO,
                   "p_invol_renovacao": C.P_INVOL_RENOVACAO},
        "sobrevivencia_verdade": sv,
        "cif_verdade_m12": cif,
    }


def salvar_ground_truth(gt: dict) -> None:
    C.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    C.GROUND_TRUTH_JSON.write_text(json.dumps(gt, indent=2, ensure_ascii=False), encoding="utf-8")


def salvar_dataset(df: pd.DataFrame) -> None:
    C.DATA_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(C.DATASET_CSV, index=False, encoding="utf-8", date_format="%Y-%m-%d")


def carregar_dataset() -> pd.DataFrame:
    df = pd.read_csv(C.DATASET_CSV, encoding="utf-8", parse_dates=["data_inicio", "data_cancelamento"])
    df["causa"] = df["causa"].fillna("")
    return df
