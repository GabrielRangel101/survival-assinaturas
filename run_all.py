#!/usr/bin/env python
"""Ponto de entrada único: gera dados, análises, figuras, results.json, documentos e notebooks.

Uso (PowerShell):  .\\.venv\\Scripts\\python.exe run_all.py [--rapido] [--sem-notebooks] [--sem-gate]

Ordem (a mesma do relatório): A desenho -> B ingênuo x KM -> C log-rank/Holm -> D Cox -> E valor ->
F armadilhas. Só DEPOIS de a suíte de testes dos métodos passar é que a seção G (riscos competitivos)
é calculada (use --sem-gate para pular essa trava).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ / "src"))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from sobrevivencia import config as C  # noqa: E402
from sobrevivencia import docs, figures, montecarlo, notebooks, pipeline  # noqa: E402
from sobrevivencia import preditivo as PD  # noqa: E402
from sobrevivencia import simulate as S  # noqa: E402


def gate_de_testes() -> bool:
    print("Trava: rodando a suíte de testes dos métodos (pytest -m 'not docs')…", flush=True)
    r = subprocess.run([sys.executable, "-m", "pytest", "-m", "not docs", "-x", "-q"], cwd=str(RAIZ))
    return r.returncode == 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rapido", action="store_true", help="menos réplicas de bootstrap (resultados aproximados)")
    ap.add_argument("--sem-notebooks", action="store_true", help="não executar os notebooks")
    ap.add_argument("--sem-gate", action="store_true", help="não rodar os testes antes da seção G")
    args = ap.parse_args()
    n_boot = C.N_BOOT_RAPIDO if args.rapido else C.N_BOOT
    t0 = time.time()

    print(f"1/5 Dados sintéticos (seed {C.SEED}) e análises A–F (bootstrap: {n_boot} réplicas)")
    df, lat = S.simular()
    S.salvar_dataset(df)
    res, extra = pipeline.montar_resultados(df, lat, n_boot, com_riscos_competitivos=False)

    if not args.sem_gate and not gate_de_testes():
        print("\nOs testes falharam: a seção G (riscos competitivos) NÃO foi calculada e nada foi gravado.")
        return 1
    print("2/5 Seção G: riscos competitivos")
    pipeline.adicionar_riscos_competitivos(res, extra, n_boot)
    n_mc = montecarlo.MC_REPLICAS_RAPIDO if args.rapido else montecarlo.MC_REPLICAS
    print(f"    Validação do Cox corrigido em {n_mc} réplicas (seeds diferentes)")
    res["recuperacao_mc"] = montecarlo.recuperacao(n_rep=n_mc)
    n_rob, n_rob_n = (2, 5000) if args.rapido else (montecarlo.ROB_REPLICAS, montecarlo.ROB_N)
    print(f"    Robustez: mesmo modelo em dados com gerador diferente ({n_rob} réplicas por variante)")
    res["robustez_mc"] = montecarlo.robustez(n_rep=n_rob, n=n_rob_n)
    PD.pontuar(df).to_csv(C.DATA_DIR / "score_risco.csv", index=False, encoding="utf-8")
    print("    data/score_risco.csv gravado (probabilidade de cancelar em 6 meses por assinante)")
    S.salvar_ground_truth(extra["gt"])
    C.RESULTS_JSON.write_text(pipeline.serializar(res), encoding="utf-8")
    print(f"    {C.RESULTS_JSON.relative_to(RAIZ)} gravado")

    print("3/5 Figuras")
    figures.gerar_todas(df, res)
    print("4/5 Documentos (README, DECISIONS, relatório HTML, portfolio/)")
    for nome, caminho in docs.construir(res).items():
        print(f"    {nome}: {caminho.relative_to(RAIZ)}")
    if not args.sem_notebooks:
        print("5/5 Notebooks (execução de ponta a ponta)")
        notebooks.executar()
    else:
        print("5/5 Notebooks: pulados")
    print(f"\nPronto em {time.time() - t0:.0f}s. Abra report/{docs.SLUG}.html no navegador.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
