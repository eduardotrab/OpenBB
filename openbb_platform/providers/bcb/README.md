# OpenBB BCB Provider

Banco Central do Brasil (BCB) open data for the OpenBB Platform. No API key required.

## Coverage

| Command | Source | Notes |
|---|---|---|
| `obb.currency.price.historical(symbol="USDBRL", provider="bcb")` | Olinda PTAX (`CotacaoMoedaPeriodo`) | `close` = PTAX sell rate, `bid` = PTAX buy rate. `bulletin="close"` (default, one row per day) or `"all"` (opening and intermediate bulletins). Defaults to the last 30 days. |

| `obb.bcb.focus(indicator="IPCA", frequency="annual", provider="bcb")` | Olinda Expectativas (Boletim Focus) | `frequency`: `annual`, `monthly` or `selic` (per Copom meeting). `calculation_base`: `30d` (default) or `5d`. Mean, median, std dev, min, max and respondents per reference period. Defaults to the last 30 days. |

PTAX symbols are quoted in BRL: `USDBRL` or `USD`. Several symbols can be comma-separated.

## Development

```sh
uv pip install -e openbb_platform/providers/bcb
pytest openbb_platform/providers/bcb/tests            # replays recorded cassettes
pytest openbb_platform/providers/bcb/tests/test_bcb_fetchers.py --record=all  # re-record
```
