# OpenBB Tesouro Provider

Tesouro Nacional open data for the OpenBB Platform (Tesouro Transparente, ODbL). No API key required.

## Coverage

| Command | Source | Notes |
|---|---|---|
| `obb.tesouro.direto(bond="IPCA+", provider="tesouro")` | `precotaxatesourodireto.csv` (Tesouro Transparente CKAN) | Daily buy/sell rates (% a.a.) and unit prices of every Tesouro Direto bond since 2004. `bond`: case-insensitive substring (`Selic`, `IPCA+`, `Prefixado`, `Renda+`, `Educa+`, `IGPM+`). Defaults to the last 30 days. |

The source is a single ~15 MB file (slow server, ~80 s) updated daily around 10:30 BRT; it is cached on disk for 12 hours (`OPENBB_TESOURO_CACHE_DIR`, default `~/.cache/openbb_tesouro`; `use_cache=False` to bypass).

## Development

```sh
uv pip install -e openbb_platform/providers/tesouro
pytest openbb_platform/providers/tesouro/tests         # offline
pytest openbb_platform/providers/tesouro/integration   # live, downloads the file
```
