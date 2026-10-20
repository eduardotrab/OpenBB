# brasil-painel

Painel próprio (Dash) que lê a API OpenBB local (`127.0.0.1:6900`). Tudo é servido pela própria máquina: nenhum CDN, fonte ou script externo.

```sh
uv pip install --python ../.venv -e ".[test]"
../.venv/bin/painel                 # desenvolvimento, http://127.0.0.1:6902
../.venv/bin/python -m pytest -q    # testes
```

Configuração por variáveis de ambiente (ver `brasil_painel/config.py`): `PAINEL_HOST`, `PAINEL_PORT`, `OPENBB_API_URL`.
