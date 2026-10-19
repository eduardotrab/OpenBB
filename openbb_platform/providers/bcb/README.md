# OpenBB BCB Provider

Banco Central do Brasil (BCB) open data for the OpenBB Platform. No API key required.

## Coverage

| Command | Source | Notes |
|---|---|---|
| `obb.currency.price.historical(symbol="USDBRL", provider="bcb")` | Olinda PTAX (`CotacaoMoedaPeriodo`) | `close` = PTAX sell rate, `bid` = PTAX buy rate. `bulletin="close"` (default, one row per day) or `"all"` (opening and intermediate bulletins). Defaults to the last 30 days. |

Symbols are quoted in BRL: `USDBRL` or `USD`. Several symbols can be comma-separated.

## Development

```sh
uv pip install -e openbb_platform/providers/bcb
pytest openbb_platform/providers/bcb/tests            # replays recorded cassettes
pytest openbb_platform/providers/bcb/tests/test_bcb_fetchers.py --record=all  # re-record
```
