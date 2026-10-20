"""`painel-usuarios`: manage dashboard users (add / remove / list)."""

import argparse
import getpass
import sys

from brasil_painel.config import Settings
from brasil_painel.usuarios import UserStore


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(prog="painel-usuarios", description=__doc__)
    sub = parser.add_subparsers(dest="comando", required=True)
    sub.add_parser("add", help="cadastrar usuário (pede a senha)").add_argument("usuario")
    sub.add_parser("remove", help="remover usuário").add_argument("usuario")
    sub.add_parser("list", help="listar usuários")
    args = parser.parse_args(argv)

    store = UserStore(Settings.from_env().users_file)
    try:
        if args.comando == "add":
            senha = getpass.getpass("Senha: ")
            if senha != getpass.getpass("Repita a senha: "):
                print("As senhas não conferem.", file=sys.stderr)
                return 1
            store.add(args.usuario, senha)
            print(f"Usuário '{args.usuario}' cadastrado em {store.path}.")
        elif args.comando == "remove":
            store.remove(args.usuario)
            print(f"Usuário '{args.usuario}' removido.")
        else:
            print("\n".join(store.list()) or "(nenhum usuário)")
    except (ValueError, KeyError) as error:
        print(f"Erro: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
