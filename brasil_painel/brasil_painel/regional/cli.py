"""`painel-dados`: refresh the regional datasets of the local store."""

import argparse
import sys
import time

from brasil_painel.regional import (
    armazem,
    b3,
    cartoes,
    estban,
    ibge,
    ifdata,
    juros,
    maquininhas,
    pix,
    scr,
    sicor,
)

DATASETS = {
    "scr": scr.atualizar,
    "sicor": sicor.atualizar,
    "pix": pix.atualizar,
    "maquininhas": maquininhas.atualizar,
    "desemprego": ibge.atualizar_desemprego,
    "populacao": ibge.atualizar_populacao,
    "municipios": ibge.atualizar_municipios,
    "estban": estban.atualizar,
    "sicor_municipios": sicor.atualizar_municipios,
    "juros": juros.atualizar,
    "cartoes": cartoes.atualizar,
    "b3": b3.atualizar,
    "ifdata": ifdata.atualizar,
}


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(prog="painel-dados", description=__doc__)
    sub = parser.add_subparsers(dest="comando", required=True)
    atualizar = sub.add_parser("atualizar", help="baixar e agregar as fontes")
    atualizar.add_argument(
        "datasets", nargs="*", help=f"{', '.join(DATASETS)} (padrão: todos)"
    )
    atualizar.add_argument(
        "--anos", type=int, nargs="+", help="padrão: ano passado e atual"
    )
    args = parser.parse_args(argv)
    desconhecidos = set(args.datasets) - set(DATASETS)
    if desconhecidos:
        parser.error(f"dataset desconhecido: {', '.join(sorted(desconhecidos))}")

    falhas = 0
    for nome in args.datasets or DATASETS:
        inicio = time.monotonic()
        try:
            df = DATASETS[nome](anos=args.anos)
        except Exception as error:  # noqa: BLE001 - one source must not stop the others
            print(f"{nome}: ERRO {error}", file=sys.stderr)
            falhas += 1
            continue
        print(
            f"{nome}: {len(df)} linhas, até {df['data'].max()}"
            f" ({time.monotonic() - inicio:.0f} s) → {armazem.diretorio()}"
        )
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
