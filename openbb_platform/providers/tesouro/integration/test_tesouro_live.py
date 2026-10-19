"""Live test against Tesouro Transparente (downloads ~15 MB; not in the default suite)."""

import datetime

import pytest
from openbb_core.app.service.user_service import UserService

from openbb_tesouro.models.direto import TesouroDiretoFetcher

test_credentials = UserService().default_user_settings.credentials.model_dump(
    mode="json"
)


@pytest.mark.integration
def test_tesouro_direto_fetcher_live(credentials=test_credentials):
    params = {
        "bond": "Selic",
        "start_date": datetime.date(2026, 10, 1),
        "end_date": datetime.date(2026, 10, 15),
    }

    fetcher = TesouroDiretoFetcher()
    result = fetcher.test(params, credentials)
    assert result is None
