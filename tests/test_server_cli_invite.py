"""scpi-web invite: one command that prints a link and a code."""

import pytest

from scpi_control.server.__main__ import main
from scpi_control.server.auth import TokenStore
from scpi_control.server.invitations import InvitationStore


def test_invite_prints_a_link_and_a_code(tmp_path, capsys):
    main(["invite", "bob", "--config-dir", str(tmp_path)])
    printed = capsys.readouterr().out
    assert "?invite=" in printed
    assert InvitationStore(str(tmp_path / "invitations.json")).pending() == 1


def test_invite_prints_no_raw_token(tmp_path, capsys):
    # A token is minted at redemption, not at invitation. If one ever appears
    # here, the long-lived secret is back in the chat message.
    main(["invite", "bob", "--config-dir", str(tmp_path)])
    printed = capsys.readouterr().out
    assert "scpi_" not in printed
    assert TokenStore(str(tmp_path / "tokens.json")).names() == []


def test_the_printed_code_actually_redeems(tmp_path, capsys):
    main(["invite", "bob", "--config-dir", str(tmp_path)])
    printed = capsys.readouterr().out
    digits = "".join(char for char in printed.split("code:")[1] if char.isdigit() or char == "\n").split("\n")[0]
    assert InvitationStore(str(tmp_path / "invitations.json")).redeem(code=digits) == "bob"


def test_invite_uses_the_url_the_gateway_recorded(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr("scpi_control.server.__main__._run_servers", lambda main_app, host, port, admin_app, admin_port: None)
    # The store is empty here, so main() would otherwise try to open a real
    # browser on the setup screen -- stub it the same as the first-run tests do.
    monkeypatch.setattr("scpi_control.server.__main__._open_browser", lambda url: True)
    main(["--config-dir", str(tmp_path), "--host", "192.168.1.50", "--port", "9000"])
    capsys.readouterr()
    main(["invite", "bob", "--config-dir", str(tmp_path)])
    assert "http://192.168.1.50:9000/?invite=" in capsys.readouterr().out


def test_invite_falls_back_with_a_note_when_no_gateway_has_run(tmp_path, capsys):
    main(["invite", "bob", "--config-dir", str(tmp_path)])
    printed = capsys.readouterr().out
    assert "127.0.0.1:8765" in printed
    assert "--url" in printed


def test_url_override_wins(tmp_path, capsys):
    main(["invite", "bob", "--url", "http://lab-pc:1234/", "--config-dir", str(tmp_path)])
    assert "http://lab-pc:1234/?invite=" in capsys.readouterr().out


def test_invite_with_an_empty_name_exits_nonzero(tmp_path):
    with pytest.raises(SystemExit) as excinfo:
        main(["invite", "", "--config-dir", str(tmp_path)])
    assert excinfo.value.code != 0


def test_config_dir_before_subcommand_is_used_for_invite(tmp_path, capsys):
    # The argparse SUPPRESS trap documented in __main__._add_config_dir bit
    # every token subcommand once already; a new subparser is a new chance to
    # send an invitation into the developer's real ~/.siglent.
    main(["--config-dir", str(tmp_path), "invite", "bob"])
    capsys.readouterr()
    assert (tmp_path / "invitations.json").exists()


def test_a_corrupt_invitation_file_stops_serve_before_a_token_is_minted(tmp_path, capsys, monkeypatch):
    # The invitation store used to be built inside the create_app(...) call,
    # after the bootstrap mint and after "Gateway ready. Open: ...?token=...".
    # So a corrupt invitations.json printed a URL for a server that never
    # started AND left a live token behind -- and because the token store was
    # no longer empty, no later start would ever print that URL again. Exiting
    # is not enough to assert: the token is the damage.
    monkeypatch.setattr(
        "scpi_control.server.__main__._run_servers",
        lambda main_app, host, port, admin_app, admin_port: pytest.fail("uvicorn should not have started"),
    )
    (tmp_path / "invitations.json").write_text("{ not json")
    with pytest.raises(SystemExit) as excinfo:
        main(["--config-dir", str(tmp_path)])
    assert excinfo.value.code != 0
    assert TokenStore(str(tmp_path / "tokens.json")).names() == []
    assert "?token=" not in capsys.readouterr().out


def test_serve_prints_the_url_every_time_not_just_the_first(tmp_path, capsys, monkeypatch):
    # "The first" used to mean "the bootstrap mint": the store started empty
    # and the first main() call minted "default" into it, so a second call
    # was needed to reach the established-store branch. There is no more
    # auto-mint, so a store established by scpi-web invite/token add is set
    # up directly here, and both calls exercise the same (only) established
    # branch -- the regression this guards against is a run silently
    # dropping the URL, whichever call it is.
    monkeypatch.setattr("scpi_control.server.__main__._run_servers", lambda main_app, host, port, admin_app, admin_port: None)
    TokenStore(str(tmp_path / "tokens.json")).mint("robin")
    main(["--config-dir", str(tmp_path), "--port", "9999"])
    capsys.readouterr()
    main(["--config-dir", str(tmp_path), "--port", "9999"])
    printed = capsys.readouterr().out
    assert "9999" in printed
    assert "invite" in printed
