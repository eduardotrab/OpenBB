"""Client of the local OpenBB API: results, tolerant JSON, cache and errors."""

import pytest
import requests

from brasil_painel.dados.api import FonteIndisponivel, OpenBBClient


class FakeResponse:
    def __init__(self, text, status=200):
        self.text, self.status_code = text, status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))


@pytest.fixture
def chamadas(monkeypatch):
    registro = []

    def fake_get(self, url, params=None, timeout=None):
        registro.append((url, params))
        return registro_respostas.pop(0)

    registro_respostas: list = []
    monkeypatch.setattr(requests.Session, "get", fake_get)
    return registro, registro_respostas


def test_returns_results_and_tolerates_control_characters(chamadas):
    registro, respostas = chamadas
    respostas.append(FakeResponse('{"results": [{"title": "a\tb\x01"}]}'))
    client = OpenBBClient("http://api/api/v1")
    assert client.get("news/rss", outlet="gov_br") == [{"title": "a\tb\x01"}]
    assert registro == [("http://api/api/v1/news/rss", {"outlet": "gov_br"})]


def test_caches_within_ttl(chamadas):
    registro, respostas = chamadas
    respostas.append(FakeResponse('{"results": [1]}'))
    client = OpenBBClient("http://api/api/v1", ttl_segundos=60)
    assert client.get("x", a=1) == client.get("x", a=1) == [1]
    assert len(registro) == 1


def test_errors_become_fonte_indisponivel(chamadas):
    _, respostas = chamadas
    respostas.append(FakeResponse('{"detail": "Unexpected Error"}', status=500))
    with pytest.raises(FonteIndisponivel):
        OpenBBClient("http://api/api/v1").get("x")


def test_empty_results_raise(chamadas):
    _, respostas = chamadas
    respostas.append(FakeResponse('{"results": []}'))
    with pytest.raises(FonteIndisponivel):
        OpenBBClient("http://api/api/v1").get("x")
