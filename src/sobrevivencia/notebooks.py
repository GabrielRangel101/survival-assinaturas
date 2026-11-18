"""Constrói e executa os dois notebooks (exploração e análise) com nbformat/nbclient."""

from __future__ import annotations

from pathlib import Path

import nbformat as nbf
from nbformat.v4 import new_code_cell as code
from nbformat.v4 import new_markdown_cell as md
from nbformat.v4 import new_notebook

from . import config as C

SETUP = '''import sys, warnings
from pathlib import Path
warnings.filterwarnings("ignore")
raiz = Path.cwd().resolve().parent if Path.cwd().name == "notebooks" else Path.cwd().resolve()
sys.path.insert(0, str(raiz / "src"))

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from IPython.display import Image, display

from sobrevivencia import config as C, simulate as S, km as K, cohorts as H, cox as X
from sobrevivencia import value as V, pitfalls as P, competing as G, figures as F

pd.options.display.float_format = "{:,.3f}".format
pd.options.display.max_columns = 30
F._estilo()
df, lat = S.simular()
gt = S.construir_ground_truth(df, lat)
import tempfile
FIG = Path(tempfile.mkdtemp(prefix='figuras_nb_'))
print(f"{len(df):,} assinantes | seed {C.SEED} | corte {C.CORTE}")'''


def _nb01() -> nbf.NotebookNode:
    c = [
        md("# 01 · Exploração dos dados sintéticos\n\n"
           "**Gazeta Meridiano** é uma empresa fictícia; os dados são 100% sintéticos (seed fixa). Este notebook explora o conjunto antes da "
           "análise formal: atributos, entradas, censura à direita e as primeiras curvas. A análise A–H está no notebook 02."),
        code(SETUP),
        md("## Os dados\n\nUma linha por assinante. `duracao_meses` é o tempo observado e `evento` vale 1 se cancelou e 0 se foi censurado no corte."),
        code("df.head(8)"),
        code("df.describe(include='all').T[['count', 'unique', 'top', 'mean', 'min', 'max']]"),
        md("## Entradas e campanhas\n\nA intensidade de entrada tem picos nas campanhas (Black Friday 2024 e 2025, Passe Copa e Eleições 2026)."),
        code("""entradas = df.groupby(df['data_inicio'].dt.to_period('M')).size()
fig, ax = plt.subplots(figsize=(10, 3.4))
ax.bar(entradas.index.astype(str), entradas.values, color=C.COR['meridiano'])
ax.set_title('Novos assinantes por mês de entrada'); ax.tick_params(axis='x', rotation=70)
plt.show()
entradas.describe()"""),
        code("""mix = pd.crosstab(df['safra'], df['canal'], normalize='index')
mix.style.format('{:.1%}').background_gradient(cmap='Blues', axis=None)"""),
        code("pd.concat({c: df[c].value_counts(normalize=True) for c in ['plano', 'oferta_entrada', 'dispositivo']}, axis=1)"),
        md("## Censura à direita\n\n"
           "O corte é fixo, então quem entrou tarde tem pouco tempo de observação. A figura mostra a vida de 40 assinantes: "
           "`x` = cancelou, círculo vazado = censurado (ainda ativo no corte)."),
        code("""amostra = df.sample(40, random_state=C.SEED).sort_values('data_inicio')
fig, ax = plt.subplots(figsize=(10, 5))
for i, (_, r) in enumerate(amostra.iterrows()):
    ax.hlines(i, 0, r['duracao_meses'], color=C.COR['meridiano'], lw=1.4)
    ax.plot(r['duracao_meses'], i, 'x' if r['evento'] else 'o', color=C.COR['vermelho'] if r['evento'] else C.COR['cinza'],
            mfc='none' if not r['evento'] else None)
ax.set_xlabel('meses desde a primeira cobrança'); ax.set_yticks([]); ax.set_title('Linhas de vida (x = cancelou, o = censurado)')
plt.show()"""),
        code("""cens = df.groupby('safra').agg(n=('evento', 'size'), cancelaram=('evento', 'sum'), seguimento_min=('seguimento_max_meses', 'min'),
                               seguimento_max=('seguimento_max_meses', 'max'))
cens['pct_censurado'] = 1 - cens['cancelaram'] / cens['n']
cens"""),
        md("## Primeiras curvas\n\nKaplan-Meier de toda a base e por plano. O plano anual quase não cai até o mês 12 e depois despenca na renovação."),
        code("""fig, ax = plt.subplots(figsize=(9, 4.6))
F._curva_km(ax, df, C.COR['tinta'], 'Todos')
for p in C.PLANOS:
    F._curva_km(ax, df[df['plano'] == p], C.COR_PLANO[p], C.PLANOS_ROTULO[p], ic=False)
ax.set_xlim(0, 24); ax.set_ylim(0, 1.02); ax.legend(); ax.set_xlabel('meses'); ax.set_title('Kaplan-Meier: base inteira e por plano')
plt.show()"""),
        md("## Risco empírico por mês de vida\n\nO risco mensal (eventos ÷ tempo sob risco) mostra o **penhasco** da promoção: "
           "quem entrou pela Black Friday cancela muito mais no mês 3–4, o primeiro a preço cheio."),
        code("""na = df[df['plano'] != 'anual']
bf, ref = na[na['oferta_entrada'] == 'black_friday'], na[na['oferta_entrada'] == 'nenhuma']
tab = pd.DataFrame({'sem_promocao': [r['taxa'] for r in K.hazard_por_idade(ref['duracao_meses'], ref['evento'], 12)],
                    'black_friday': [r['taxa'] for r in K.hazard_por_idade(bf['duracao_meses'], bf['evento'], 12)]})
tab.index.name = 'mês de vida'
ax = tab.plot(drawstyle='steps-post', figsize=(9, 3.8), color=[C.COR['meridiano'], C.COR['vermelho']])
ax.set_ylabel('risco mensal'); ax.set_title('Risco mensal de cancelar por mês de vida'); plt.show()
tab.round(4)"""),
        md("## O que o KM recupera da verdade plantada\n\nComo o gerador é conhecido, dá para comparar o KM por canal com a sobrevivência verdadeira."),
        code("""linhas = []
for c in C.CANAIS:
    sub = df[df['canal'] == c]
    for h in (12, 18):
        p = K.km_ponto(sub['duracao_meses'], sub['evento'], h)
        v = gt['sobrevivencia_verdade']['por_canal'][c][f'm{h}']['todos']
        linhas.append({'canal': C.CANAIS_ROTULO[c], 'h': f'M{h}', 'KM': p['valor'], 'IC_lo': p['lo'], 'IC_hi': p['hi'], 'verdade': v,
                       'cobre': p['lo'] <= v <= p['hi']})
pd.DataFrame(linhas)"""),
        md("## Próximo passo\n\nO notebook **02 · Análise** aplica o desenho A–H: ingênuo × KM por safra, log-rank, Cox com a violação mostrada e corrigida, "
           "valor por canal, armadilhas e riscos competitivos."),
    ]
    return new_notebook(cells=c, metadata={"kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"}})


def _nb02() -> nbf.NotebookNode:
    c = [
        md("# 02 · Análise de sobrevivência (A–H)\n\n"
           "Mesma ordem do relatório HTML: **A** desenho · **B** ingênuo × Kaplan-Meier · **C** comparações · **D** Cox · **E** valor por canal · "
           "**F** o que poderia ter dado errado · **G** riscos competitivos (só depois de os testes passarem) · **H** limites. "
           "Para ser rápido, o bootstrap usa poucas réplicas aqui; `python run_all.py` usa o número completo."),
        code(SETUP + "\nN_BOOT = 200"),
        md("## A. Desenho\n\n**Evento**: cancelamento efetivo. **Origem do tempo**: primeira cobrança. **Corte**: fixo em 31/10/2026. **Censura**: à direita."),
        code("pd.Series(H.resumo_dados(df)).to_frame('valor')"),
        md("## B. O erro clássico: retenção ingênua × Kaplan-Meier por safra\n\n"
           "Só publicamos M12/M18/M24 onde **todos** os membros da safra tiveram tempo de ser observados (e há assinantes sob risco suficientes)."),
        code("""tab = H.tabela_safras(df)
linhas = []
for l in tab['safras']:
    r = {'safra': l['safra'], 'n': l['n'], 'ingenua': l['ret_ingenua']}
    for h in ('m3', 'm6', 'm12', 'm18', 'm24'):
        p = l['horizontes'][h]; r[f'KM {h}'] = p['valor'] if p['ok'] else np.nan
        if h in ('m12', 'm18', 'm24'): r[f'status {h}'] = p['status'] or '—'
    linhas.append(r)
pd.DataFrame(linhas).set_index('safra')"""),
        code("""print(f"Spearman(ingênua, idade da safra) = {tab['rho_ingenua_idade']:.2f}  |  Spearman(KM M3, idade) = {tab['rho_km_m3_idade']:.2f}")
res_b = {'ingenuo_vs_km': tab}
display(Image(str(F.fig_ingenua_vs_km(res_b, FIG))))"""),
        md("## C. Comparações: log-rank e Holm"),
        code("""comp = H.comparacoes(df)
pd.DataFrame({k: v['logrank'] for k, v in comp.items()}).T"""),
        code("""pares = pd.DataFrame(comp['canal']['pares'])[['rotulo_a', 'rotulo_b', 'chi2', 'p', 'p_holm', 'significativo_holm']]
pares"""),
        code("""print({k: (v['n_sig_bruto'], v['n_sig_holm'], v['n_pares']) for k, v in comp.items()}, '(bruto, Holm, pares)')
display(Image(str(F.fig_km_grupos(df, 'canal', C.CANAIS, C.CANAIS_ROTULO, C.COR_CANAL, 'Sobrevivência por canal', FIG, 'km_canal.png'))))"""),
        md("## D. Cox: mostrar a violação, corrigir e comparar com o plantado"),
        code("""cph_i, d_i = X.ajustar_ingenuo(df)
covs_i = [c for c in d_i.columns if c not in ('duracao', 'evento')]
ph_i = X.teste_ph(d_i, covs_i, cph_i.params_[covs_i].to_numpy(), stop='duracao', evento='evento')
tab_i = pd.DataFrame(X.tabela_hr(cph_i)).set_index('nome')[['hr', 'lo', 'hi', 'verdade']]
tab_i.join(pd.DataFrame(X.resumo_ph(ph_i, covs_i)).set_index('nome')[['p_rank', 'p_faixas', 'viola']])"""),
        code("""print('Teste global de Schoenfeld (ingênuo):', ph_i['global_rank'])
print('C-index (ingênuo):', round(cph_i.concordance_index_, 3))
print('Efeito local da promoção por faixa de idade:', [(x['ini'], round(x['hr_local'], 2)) for x in ph_i['efeito_local']['oferta_bf']])"""),
        code("""ep = X.episodios(df)
cph_c, d_c = X.ajustar_corrigido(ep)
covs_c = X.COVS_CORRIGIDO
ph_c = X.teste_ph(d_c, covs_c, cph_c.params_[covs_c].to_numpy(), stop='stop', evento='evento', start='start', strata='plano')
print('Episódios:', len(ep), '| Teste global (corrigido):', ph_c['global_rank'])
pd.DataFrame(X.tabela_hr(cph_c)).set_index('nome')[['hr', 'lo', 'hi', 'verdade', 'cobre', 'erro_rel']]"""),
        code("""cph_p, _ = X.ajustar_complementar(df, ep)
print('HR de plano (modelo sem o anual):')
pd.DataFrame([r for r in X.tabela_hr(cph_p) if r['nome'].startswith('plano')]).set_index('nome')[['hr', 'lo', 'hi', 'verdade', 'cobre']]"""),
        md("## E. Valor por canal: RMST, LTV descontado, CAC e payback\n\nARPU, CAC e taxa de desconto são **premissas** (`config.py`). Medido = coberto pelo KM; projetado = cauda extrapolada."),
        code("""valor = V.analise_valor(df, n_boot=N_BOOT)
pd.DataFrame([{'canal': c['rotulo'], 'CAC': c['cac'], 'RMST_24m': c['rmst']['est'], 'LTV_24m': c['ltv']['est'],
               'LTV_lo': c['ltv']['lo'], 'LTV_hi': c['ltv']['hi'], '% medido': c['pct_ltv_medido'],
               'LTV/CAC': c['ltv_cac']['est'], 'payback (mens.)': c['payback']['est']} for c in valor['canais']]).set_index('canal')"""),
        code("""print('Ranking só por CAC (canais com verba):      ', valor['ranking_cac'])
print('Ranking por LTV/CAC (com permanência):       ', valor['ranking_ltv_cac'])
dec = V.decisao_verba(valor)
print(f"Realocar R$ {dec['verba_exemplo']:,.0f} do pior para o melhor: +R$ {dec['ganho_realocar_pior_para_melhor']:,.0f} de valor líquido (PROJETADO)")
acao = V.acao_mes3(df, X.tabela_hr(cph_c))
print('MEDIDO  -> prob. de cancelar no mês 3-4 (Black Friday):', round(acao['medido']['q_penhasco'], 3))
p = acao['projetado']
print(f"PROJETADO -> ação de R$ {p['custo_por_assinante']:.0f}/assinante: líquido R$ {p['base']['liquido']:,.0f} com efetividade {p['efetividade_base']:.0%}; "
      f"equilíbrio em {p['efetividade_equilibrio']:.0%}")"""),
        md("## F. O que poderia ter dado errado"),
        code("""pd.DataFrame(P.censura_ignorada(df, gt)['metodos'])[['rotulo', 'valor', 'erro_pp']]"""),
        code("""bf = next(r for r in X.resumo_ph(ph_i, covs_i) if r['nome'] == 'oferta_bf')
pv = P.ph_violada(df, float(np.exp(cph_i.params_['oferta_bf'])), X.tabela_hr(cph_c), bf['p_faixas'], bf['p_rank'])
print({k: round(v, 4) for k, v in pv.items() if isinstance(v, float)})"""),
        code("""rk = P.ranking_m12_bruto(df, gt)
print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in rk.items() if k != 'safras_reais'})"""),
        md("## G. Riscos competitivos (Aalen-Johansen)\n\n"
           "Seção feita **depois** que os testes das etapas anteriores passaram (`python run_all.py` aplica essa trava antes de calcular a seção G)."),
        code("""rc = G.analise(df, gt, n_boot=100)
pd.DataFrame({m: {k: v['est'] for k, v in pts.items() if isinstance(v, dict)} for m, pts in rc['pontos'].items()})"""),
        code("""res_g = {'riscos_competitivos': rc}
display(Image(str(F.fig_riscos_competitivos(res_g, FIG))))"""),
        md("## H. Limites honestos\n\n"
           "- Dados sintéticos e efeitos plantados: o notebook mostra que o método recupera o efeito certo, não uma descoberta sobre o mundo.\n"
           "- M24 não é observável com esta janela.\n"
           "- ARPU, CAC, taxa de desconto e a efetividade da ação do mês 3 são premissas.\n"
           "- O KM agregado mistura safras com riscos diferentes; o reajuste de preço é associação, não causalidade."),
    ]
    return new_notebook(cells=c, metadata={"kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"}})


NOTEBOOKS = {"01_exploracao.ipynb": _nb01, "02_analise.ipynb": _nb02}


def construir(pasta: Path = C.NOTEBOOKS_DIR) -> list[Path]:
    pasta.mkdir(parents=True, exist_ok=True)
    out = []
    for nome, fn in NOTEBOOKS.items():
        p = pasta / nome
        nbf.write(fn(), str(p))
        out.append(p)
    return out


def executar(pasta: Path = C.NOTEBOOKS_DIR, timeout: int = 900, log=print) -> list[Path]:
    """Constrói e executa os notebooks do início ao fim, gravando as saídas."""
    from nbclient import NotebookClient

    out = []
    for p in construir(pasta):
        nb = nbf.read(str(p), as_version=4)
        log(f"  executando {p.name}…")
        NotebookClient(nb, timeout=timeout, kernel_name="python3", resources={"metadata": {"path": str(pasta)}}).execute()
        nbf.write(nb, str(p))
        out.append(p)
    return out


if __name__ == "__main__":
    for p in executar():
        print(p)
