"""First run: no auto-minted identity, and a route to the setup screen."""

import pytest

from scpi_control.server.__main__ import main
from scpi_control.server.auth import TokenStore


@pytest.fixture
def served(monkeypatch):
    calls = {}
    monkeypatch.setattr(
        "scpi_control.server.__main__._run_servers",
        lambda main_app, host, port, admin_app, admin_port: calls.update(admin_app=admin_app, admin_port=admin_port),
    )
    return calls


def test_an_empty_store_mints_nothing(served, tmp_path, monkeypatch):
    # The old behaviour minted an identity literally called "default", which
    # then showed up as the owner of every session created from it. Setup mints
    # a real name instead.
    monkeypatch.setattr("scpi_control.server.__main__._open_browser", lambda url: True)
    main(["--config-dir", str(tmp_path)])
    assert TokenStore(str(tmp_path / "tokens.json")).names() == []


def test_an_empty_store_opens_the_admin_panel(served, tmp_path, monkeypatch):
    opened = {}
    monkeypatch.setattr("scpi_control.server.__main__._open_browser", lambda url: opened.setdefault("url", url) or True)
    main(["--config-dir", str(tmp_path), "--admin-port", "9100"])
    assert opened["url"] == "http://127.0.0.1:9100/"


def test_a_configured_store_does_not_open_a_browser(served, tmp_path, monkeypatch):
    # Opening a window on every restart of a working gateway would be
    # obnoxious; the setup screen is for the first run only.
    opened = {}
    monkeypatch.setattr("scpi_control.server.__main__._open_browser", lambda url: opened.setdefault("url", url) or True)
    TokenStore(str(tmp_path / "tokens.json")).mint("robin")
    main(["--config-dir", str(tmp_path)])
    assert opened == {}


def test_a_browser_that_will_not_open_does_not_fail_the_start(served, tmp_path, monkeypatch, capsys):
    def boom(url):
        raise OSError("no display")

    monkeypatch.setattr("scpi_control.server.__main__._open_browser", boom)
    main(["--config-dir", str(tmp_path)])
    printed = capsys.readouterr().out
    assert "8766" in printed
    assert served["admin_app"] is not None


def test_no_admin_on_an_empty_store_points_at_the_cli(served, tmp_path, capsys):
    # Without this branch the combination is a running gateway nobody can ever
    # reach: no auto-minted token, and no panel to make one.
    main(["--config-dir", str(tmp_path), "--no-admin"])
    printed = capsys.readouterr().out
    assert "scpi-web invite" in printed
    assert TokenStore(str(tmp_path / "tokens.json")).names() == []


def test_no_token_url_is_printed_any_more(served, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("scpi_control.server.__main__._open_browser", lambda url: True)
    main(["--config-dir", str(tmp_path)])
    assert "?token=" not in capsys.readouterr().out
