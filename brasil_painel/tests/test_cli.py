"""`painel-usuarios` command."""

from brasil_painel import cli
from brasil_painel.usuarios import UserStore


def test_add_list_remove(tmp_path, monkeypatch, capsys):
    path = tmp_path / "u.json"
    monkeypatch.setenv("PAINEL_USERS_FILE", str(path))
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt="": "senha-forte-123")
    assert cli.main(["add", "ana"]) == 0
    assert UserStore(path).verify("ana", "senha-forte-123")
    assert cli.main(["list"]) == 0
    assert "ana" in capsys.readouterr().out
    assert cli.main(["remove", "ana"]) == 0
    assert cli.main(["remove", "ana"]) == 1
