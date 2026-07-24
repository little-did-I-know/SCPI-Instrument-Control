"""scpi-web token subcommands and first-run bootstrap."""

import pytest

from scpi_control.server.__main__ import main
from scpi_control.server.auth import TokenStore


def test_token_add_prints_the_raw_token_once(tmp_path, capsys):
    main(["token", "add", "robin", "--config-dir", str(tmp_path)])
    printed = capsys.readouterr().out
    assert "scpi_" in printed
    raw = [word for word in printed.split() if word.startswith("scpi_")][0]
    assert TokenStore(str(tmp_path / "tokens.json")).verify(raw) == "robin"


def test_token_list_shows_names_not_secrets(tmp_path, capsys):
    main(["token", "add", "robin", "--config-dir", str(tmp_path)])
    capsys.readouterr()
    main(["token", "list", "--config-dir", str(tmp_path)])
    printed = capsys.readouterr().out
    assert "robin" in printed
    assert "scpi_" not in printed


def test_token_revoke_removes_it(tmp_path, capsys):
    main(["token", "add", "robin", "--config-dir", str(tmp_path)])
    main(["token", "revoke", "robin", "--config-dir", str(tmp_path)])
    assert TokenStore(str(tmp_path / "tokens.json")).names() == []


def test_revoking_unknown_name_exits_nonzero(tmp_path):
    with pytest.raises(SystemExit) as excinfo:
        main(["token", "revoke", "ghost", "--config-dir", str(tmp_path)])
    assert excinfo.value.code != 0


def test_duplicate_name_exits_nonzero(tmp_path):
    main(["token", "add", "robin", "--config-dir", str(tmp_path)])
    with pytest.raises(SystemExit) as excinfo:
        main(["token", "add", "robin", "--config-dir", str(tmp_path)])
    assert excinfo.value.code != 0


def test_serve_bootstraps_a_token_and_prints_url(tmp_path, capsys, monkeypatch):
    started = {}
    monkeypatch.setattr("uvicorn.run", lambda app, host, port: started.update(host=host, port=port))
    main(["--config-dir", str(tmp_path), "--port", "9999"])
    printed = capsys.readouterr().out
    assert "?token=scpi_" in printed
    assert started["port"] == 9999
    assert TokenStore(str(tmp_path / "tokens.json")).names() == ["default"]


def test_serve_does_not_remint_when_tokens_exist(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr("uvicorn.run", lambda app, host, port: None)
    main(["token", "add", "robin", "--config-dir", str(tmp_path)])
    capsys.readouterr()
    main(["--config-dir", str(tmp_path)])
    assert TokenStore(str(tmp_path / "tokens.json")).names() == ["robin"]
    assert "?token=" not in capsys.readouterr().out
