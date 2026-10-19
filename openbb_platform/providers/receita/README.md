# OpenBB Receita Federal Provider

Receita Federal do Brasil open data for the OpenBB Platform. No API key required.

## Coverage

| Command | Source | Notes |
|---|---|---|
| `obb.receita.revenue(uf="SP", tax="IRPF", provider="receita")` | `gov.br/receitafederal/dados/arrecadacao-estado.csv` | Monthly federal tax revenue by state since 2000, long format (one row per month, UF and tax line; nominal BRL). `uf` comma-separated; `tax` case and accent insensitive substring. Defaults to last year and the current year. Cached 24 h. |

Data caveats:
- gov.br answers **401 to `Accept: application/json`** (the OpenBB HTTP default), so the download sends `Accept: text/csv,*/*`.
- The file **mixes number formats by era**: up to 2002 commas are thousands separators (`47,953,915`, except `12,5`-style decimals); from 2003 on it is Brazilian (`226.708.856,85`). The parser follows that rule (validated: no scale break across 2000–2004).

## Development

```sh
uv pip install -e openbb_platform/providers/receita
pytest openbb_platform/providers/receita/tests         # offline
pytest openbb_platform/providers/receita/integration   # live
```
