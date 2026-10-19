# OpenBB BCB Provider

Banco Central do Brasil (BCB) open data for the OpenBB Platform. No API key required.

## Coverage

| Command | Source | Notes |
|---|---|---|
| `obb.currency.price.historical(symbol="USDBRL", provider="bcb")` | Olinda PTAX (`CotacaoMoedaPeriodo`) | `close` = PTAX sell rate, `bid` = PTAX buy rate. `bulletin="close"` (default, one row per day) or `"all"` (opening and intermediate bulletins). Defaults to the last 30 days. |

| `obb.bcb.focus(indicator="IPCA", frequency="annual", provider="bcb")` | Olinda Expectativas (Boletim Focus) | `frequency`: `annual`, `monthly` or `selic` (per Copom meeting). `calculation_base`: `30d` (default) or `5d`. Mean, median, std dev, min, max and respondents per reference period. Defaults to the last 30 days. |
| `obb.bcb.ifdata(period="202606", report=1, provider="bcb")` | Olinda IF.data (`IfDataCadastro` + `IfDataValores`) | Quarterly reports (1 = Resumo ... 16) joined with the cadastro. Defaults: latest published quarter, `institution_type="individual"`, `segment="cooperatives"` (Tcb B3S/B3C). Filters: `institution` (CNPJ), `uf`. Long format (one row per institution and column). Responses cached on disk for 7 days (`OPENBB_BCB_CACHE_DIR`, default `~/.cache/openbb_bcb`; `use_cache=False` to bypass). |
| `obb.bcb.sgs(symbol="selic_target,cdi", provider="bcb")` | SGS REST (`api.bcb.gov.br/dados/serie`) | Codes or known names (`usd_brl`, `selic`, `cdi`, `igpm`, `selic_target`, `ipca`, `coop_*`). Requests split in 10-year windows. **The BCB firewall answers some networks with an HTML page (HTTP 200)**: the command raises a clear error in that case. Live-verified: pending (blocked from the development network). |
| `obb.news.world(provider="bcb", category="press_releases")` | BCB site API (`/api/servico/sitebcb/...`) | `category`: `press_releases` (notas à imprensa), `news` (notícias, with body text) or `copom` (latest `limit` Copom statements, default 10, ignoring dates). The site API returns the latest 100 items; dates and `limit` are applied client-side. |

PTAX symbols are quoted in BRL: `USDBRL` or `USD`. Several symbols can be comma-separated.

## Development

```sh
uv pip install -e openbb_platform/providers/bcb
pytest openbb_platform/providers/bcb/tests            # replays recorded cassettes
pytest openbb_platform/providers/bcb/tests/test_bcb_fetchers.py --record=all  # re-record
```
