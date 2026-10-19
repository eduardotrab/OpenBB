# OpenBB CVM Provider

CVM (Comissão de Valores Mobiliários) open data for the OpenBB Platform. No API key required.

## Coverage

| Command | Source | Notes |
|---|---|---|
| `obb.cvm.funds(search="sicoob", provider="cvm")` | `FI/CAD/DADOS/registro_fundo_classe.zip` (`registro_classe.csv`, RCVM 175) | Fund class registry: name, CNPJ, CVM/ANBIMA classification, benchmark, target public, net assets. `search` is case and accent insensitive; `cnpj` filter; `active_only` (default) keeps "Em Funcionamento Normal". Cached 24 h. |
| `obb.cvm.fund_daily(cnpj="00.017.024/0001-53", provider="cvm")` | `FI/DOC/INF_DIARIO/DADOS/inf_diario_fi_AAAAMM.zip` | Daily quota, net assets, subscriptions, redemptions and shareholders. `cnpj` required (comma-separated for several funds). One zip per month in the range; cached 12 h. Defaults to the last 30 days. |

Cache: `OPENBB_CVM_CACHE_DIR` (default `~/.cache/openbb_cvm`); `use_cache=False` to bypass.

## Development

```sh
uv pip install -e openbb_platform/providers/cvm
pytest openbb_platform/providers/cvm/tests         # offline
pytest openbb_platform/providers/cvm/integration   # live
```
