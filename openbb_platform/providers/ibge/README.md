# OpenBB IBGE Provider

IBGE (Instituto Brasileiro de Geografia e Estatística) open data for the OpenBB Platform. No API key required.

## Coverage

| Command | Source | Notes |
|---|---|---|
| `obb.ibge.aggregates(table=1737, variables="63,2265", provider="ibge")` | servicodados API v3 `agregados` (SIDRA) | Any SIDRA table. `periods`: `-N` (last N, default `-12`), `YYYYMM-YYYYMM` or list. `level` (N1 Brazil, N3 state, N6 municipality...) and `locations`. Optional `classification` (e.g. `315[7169]`). Long format; SIDRA markers: `-` (absolute zero) becomes `0`; `...`, `..`, `X`, `Z` become `None`. |
| `obb.news.world(provider="ibge")` | servicodados API v3 `noticias` | Agência IBGE news. `category`: `all`, `noticia`, `release`. Date range filtered server-side; `limit` default 50. |

Useful tables: 1737 IPCA (63 monthly change, 2265 12-month change, 2266 index), 7060 IPCA by group and metro area, 6381 unemployment rate (PNAD Contínua), 5932 quarterly GDP change.

## Development

```sh
uv pip install -e openbb_platform/providers/ibge
pytest openbb_platform/providers/ibge/tests
pytest openbb_platform/providers/ibge/tests/test_ibge_fetchers.py --record=all
```
