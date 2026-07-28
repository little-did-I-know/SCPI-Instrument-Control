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


def test_serve_never_mints_a_token(tmp_path, capsys, monkeypatch):
    # The old behaviour bootstrapped an identity literally called "default"
    # on an empty store; an empty store now mints nothing at all -- see
    # tests/test_server_first_run.py for what actually happens instead.
    # (conftest.py's autouse _no_real_browser fixture keeps the empty-store
    # path here from popping a real browser window.)
    monkeypatch.setattr("scpi_control.server.__main__._run_servers", lambda main_app, host, port, admin_app, admin_port: None)
    main(["--config-dir", str(tmp_path)])
    assert TokenStore(str(tmp_path / "tokens.json")).names() == []


# --- --config-dir ordering regressions -------------------------------------
#
# argparse's subparsers action reparses the remaining argv into a fresh
# namespace and then unconditionally copies every attribute from it back
# over the outer namespace. Each `token <cmd>` subparser also declares its
# own `--config-dir` (with default=None) so it can accept the flag *after*
# the subcommand; but when the flag is given *before* the subcommand
# instead, that per-subparser default of None was clobbering the value the
# top-level parser had already parsed. `scpi-web --config-dir X token add
# name` -- a completely natural invocation -- silently fell back to the
# real ~/.siglent. Every test above places --config-dir *after* the
# subcommand, which is why none of them caught it. These assert the
# directory actually used, not merely a zero exit code.


def test_config_dir_before_subcommand_is_used_for_token_add(tmp_path, capsys):
    main(["--config-dir", str(tmp_path), "token", "add", "robin"])
    printed = capsys.readouterr().out
    raw = [word for word in printed.split() if word.startswith("scpi_")][0]
    assert (tmp_path / "tokens.json").exists()
    assert TokenStore(str(tmp_path / "tokens.json")).verify(raw) == "robin"


def test_config_dir_after_subcommand_is_used_for_token_add(tmp_path, capsys):
    main(["token", "add", "robin", "--config-dir", str(tmp_path)])
    printed = capsys.readouterr().out
    raw = [word for word in printed.split() if word.startswith("scpi_")][0]
    assert (tmp_path / "tokens.json").exists()
    assert TokenStore(str(tmp_path / "tokens.json")).verify(raw) == "robin"


def test_config_dir_before_subcommand_is_used_for_token_list(tmp_path, capsys):
    main(["--config-dir", str(tmp_path), "token", "add", "robin"])
    capsys.readouterr()
    main(["--config-dir", str(tmp_path), "token", "list"])
    printed = capsys.readouterr().out
    assert "robin" in printed
    assert (tmp_path / "tokens.json").exists()


def test_config_dir_after_subcommand_is_used_for_token_list(tmp_path, capsys):
    main(["token", "add", "robin", "--config-dir", str(tmp_path)])
    capsys.readouterr()
    main(["token", "list", "--config-dir", str(tmp_path)])
    printed = capsys.readouterr().out
    assert "robin" in printed
    assert (tmp_path / "tokens.json").exists()


def test_config_dir_before_subcommand_is_used_for_token_revoke(tmp_path):
    main(["--config-dir", str(tmp_path), "token", "add", "robin"])
    # Asserted before the revoke: otherwise a buggy resolution that sends
    # both the add and the revoke to the same *wrong* directory still leaves
    # tmp_path's (nonexistent) store trivially empty, masking the bug.
    assert (tmp_path / "tokens.json").exists()
    main(["--config-dir", str(tmp_path), "token", "revoke", "robin"])
    assert TokenStore(str(tmp_path / "tokens.json")).names() == []


def test_config_dir_after_subcommand_is_used_for_token_revoke(tmp_path):
    main(["token", "add", "robin", "--config-dir", str(tmp_path)])
    main(["token", "revoke", "robin", "--config-dir", str(tmp_path)])
    assert TokenStore(str(tmp_path / "tokens.json")).names() == []


def test_token_add_twice_adds_a_device_instead_of_failing(tmp_path, capsys):
    main(["token", "add", "bob", "--config-dir", str(tmp_path)])
    main(["token", "add", "bob", "--config-dir", str(tmp_path)])
    printed = capsys.readouterr().out
    raws = [word for word in printed.split() if word.startswith("scpi_")]
    store = TokenStore(str(tmp_path / "tokens.json"))
    assert len(raws) == 2
    assert store.verify(raws[0]) == "bob"
    assert store.verify(raws[1]) == "bob"
    assert store.names() == ["bob"]


def test_token_list_shows_device_counts(tmp_path, capsys):
    main(["token", "add", "bob", "--config-dir", str(tmp_path)])
    main(["token", "add", "bob", "--config-dir", str(tmp_path)])
    capsys.readouterr()
    main(["token", "list", "--config-dir", str(tmp_path)])
    printed = capsys.readouterr().out
    assert "bob" in printed
    assert "2" in printed
    assert "scpi_" not in printed
