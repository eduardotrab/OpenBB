"""Live test against the Receita Federal open data (not in the default suite)."""

import pytest
from openbb_core.app.service.user_service import UserService

from openbb_receita.models.revenue import ReceitaRevenueFetcher

test_credentials = UserService().default_user_settings.credentials.model_dump(
    mode="json"
)


@pytest.mark.integration
def test_receita_revenue_fetcher_live(credentials=test_credentials):
    params = {"start_year": 2026, "end_year": 2026, "uf": "SP", "tax": "IRPF"}
    assert ReceitaRevenueFetcher().test(params, credentials) is None
