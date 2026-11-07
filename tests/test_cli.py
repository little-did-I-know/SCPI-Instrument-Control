"""`scpi` unified command-line tool: subcommands, error handling, lazy imports."""

import subprocess
import sys

import numpy as np
import pytest

from scpi_control import cli
from scpi_control.waveform_io import load_waveform

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _stray_files(directory):
    # conftest drops a fake-home dir into tmp_path; anything else is the CLI's doing
    return [p for p in directory.iterdir() if p.name != "fake-home"]


def run(argv, capsys):
    code = cli.main(argv)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


# ---- idn -------------------------------------------------------------------


def test_idn_mock_prints_identity(capsys):
    code, out, err = run(["idn", "--mock"], capsys)
    assert code == 0
    assert "Siglent" in out
    assert err == ""


def test_idn_unreachable_host_is_clean_error(capsys):
    code, out, err = run(["idn", "192.0.2.1", "--timeout", "0.3"], capsys)
    assert code == 1
    assert out == ""
    assert err.startswith("error:")
    assert "Traceback" not in err


def test_idn_requires_host_or_mock(capsys):
    code, out, err = run(["idn"], capsys)
    assert code == 2
    assert "host" in err.lower()


@pytest.mark.parametrize("bad", ["-evil", "a b", "host\nname", ""])
def test_bad_host_rejected_before_connecting(bad, capsys, monkeypatch):
    monkeypatch.setattr(cli, "_open_scope", lambda *a, **k: pytest.fail("must not connect"))
    code, out, err = run(["idn", "--", bad], capsys)
    assert code == 2
    assert "invalid host" in err


# ---- capture ---------------------------------------------------------------


def test_capture_npz_roundtrip(tmp_path, capsys):
    out_file = tmp_path / "cap.npz"
    code, out, err = run(["capture", "--mock", "--channels", "1", "-o", str(out_file)], capsys)
    assert code == 0, err
    loaded = load_waveform(out_file)
    assert len(loaded.voltage) > 100
    assert float(np.ptp(loaded.voltage)) > 0.1  # real signal, not flat
    assert "cap.npz" in out


def test_capture_multiple_channels_writes_one_file_each(tmp_path, capsys):
    out_file = tmp_path / "cap.csv"
    code, out, err = run(["capture", "--mock", "--channels", "1,2", "-o", str(out_file)], capsys)
    assert code == 0, err
    assert (tmp_path / "cap_ch1.csv").exists()
    assert (tmp_path / "cap_ch2.csv").exists()
    assert not out_file.exists()


@pytest.mark.parametrize("channels", ["", "0", "abc", "1,1", "1,,2", "99"])
def test_capture_bad_channels(channels, tmp_path, capsys):
    code, out, err = run(["capture", "--mock", "--channels", channels, "-o", str(tmp_path / "x.npz")], capsys)
    assert code == 2
    assert "channel" in err.lower()
    assert not _stray_files(tmp_path)


def test_capture_unknown_extension(tmp_path, capsys):
    code, out, err = run(["capture", "--mock", "--channels", "1", "-o", str(tmp_path / "x.txt")], capsys)
    assert code == 2
    assert "extension" in err
    assert not _stray_files(tmp_path)


def test_capture_missing_output_dir(tmp_path, capsys):
    code, out, err = run(["capture", "--mock", "--channels", "1", "-o", str(tmp_path / "nope" / "x.npz")], capsys)
    assert code == 2
    assert "directory" in err


def test_capture_unreachable_host_leaves_no_file(tmp_path, capsys):
    out_file = tmp_path / "x.npz"
    code, out, err = run(["capture", "192.0.2.1", "--timeout", "0.3", "--channels", "1", "-o", str(out_file)], capsys)
    assert code == 1
    assert err.startswith("error:")
    assert not out_file.exists()


# ---- screenshot ------------------------------------------------------------


def test_screenshot_mock_bmp(tmp_path, capsys):
    out_file = tmp_path / "s.bmp"
    code, out, err = run(["screenshot", "--mock", "-o", str(out_file)], capsys)
    assert code == 0, err
    assert out_file.read_bytes()[:2] == b"BM"


def test_screenshot_png_has_png_magic(tmp_path, capsys):
    pytest.importorskip("PIL")
    out_file = tmp_path / "s.png"
    code, out, err = run(["screenshot", "--mock", "-o", str(out_file)], capsys)
    assert code == 0, err
    assert out_file.read_bytes()[:8] == PNG_MAGIC


def test_screenshot_png_without_pillow_is_clean_error(tmp_path, capsys, monkeypatch):
    monkeypatch.setitem(sys.modules, "PIL", None)
    monkeypatch.setitem(sys.modules, "PIL.Image", None)
    out_file = tmp_path / "s.png"
    code, out, err = run(["screenshot", "--mock", "-o", str(out_file)], capsys)
    assert code == 1
    assert "Pillow" in err
    assert not out_file.exists()


def test_screenshot_default_name_is_timestamped_png(tmp_path, capsys, monkeypatch):
    pytest.importorskip("PIL")
    monkeypatch.chdir(tmp_path)
    code, out, err = run(["screenshot", "--mock"], capsys)
    assert code == 0, err
    assert len(list(tmp_path.glob("screenshot_*.png"))) == 1


# ---- demo ------------------------------------------------------------------


def test_demo_prints_stats_and_ascii_plot(capsys):
    code, out, err = run(["demo"], capsys)
    assert code == 0, err
    assert "Vpp" in out
    assert "Freq" in out
    assert out.count("*") > 20  # plot drawn


def test_demo_vpp_matches_synthesized_amplitude(capsys):
    code, out, err = run(["demo", "--amplitude", "1.0"], capsys)
    assert code == 0
    line = next(line for line in out.splitlines() if line.startswith("Vpp"))
    vpp = float(line.split()[1])
    assert 1.6 < vpp < 2.4  # ~2 V peak-to-peak for 1 V amplitude


def test_demo_saves_npz(tmp_path, capsys):
    out_file = tmp_path / "demo.npz"
    code, out, err = run(["demo", "-o", str(out_file)], capsys)
    assert code == 0, err
    assert len(load_waveform(out_file).voltage) > 100


def test_demo_saves_png_plot(tmp_path, capsys):
    out_file = tmp_path / "demo.png"
    code, out, err = run(["demo", "-o", str(out_file)], capsys)
    assert code == 0, err
    assert out_file.read_bytes()[:8] == PNG_MAGIC


def test_demo_rejects_bad_signal():
    with pytest.raises(SystemExit) as exc:
        cli.main(["demo", "--signal", "bogus"])
    assert exc.value.code == 2


# ---- discover --------------------------------------------------------------


def test_discover_empty_range(capsys):
    code, out, err = run(["discover", "--cidr", "192.0.2.0/30", "--timeout", "0.2"], capsys)
    assert code == 0, err
    assert "No instruments found" in out


def test_discover_bad_cidr_is_clean_error(capsys):
    code, out, err = run(["discover", "--cidr", "not-a-cidr"], capsys)
    assert code == 1
    assert err.startswith("error:")


def test_discover_lists_hits(capsys, monkeypatch):
    fake = [{"address": "10.0.0.5", "idn": "Siglent,SDS824X HD,SN1,1.0", "manufacturer": "Siglent", "model": "SDS824X HD", "kind": "scope", "dialect": "modern"}]
    monkeypatch.setattr("scpi_control.server.discovery.discover", lambda **kw: fake)
    code, out, err = run(["discover"], capsys)
    assert code == 0
    assert "10.0.0.5" in out and "SDS824X HD" in out


# ---- plumbing --------------------------------------------------------------


def test_no_subcommand_fails_with_usage(capsys):
    code, out, err = run([], capsys)
    assert code == 2
    assert "usage" in (out + err).lower()


def test_python_dash_m_entrypoint():
    result = subprocess.run([sys.executable, "-m", "scpi_control", "idn", "--mock"], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    assert "Siglent" in result.stdout


def test_import_does_not_pull_optional_extras():
    code = "import sys\nimport scpi_control.cli\nbad = [m for m in ('PyQt6', 'reportlab', 'h5py', 'PIL', 'fastapi') if m in sys.modules]\nprint(bad)\nsys.exit(1 if bad else 0)\n"
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr


def test_unexpected_exception_is_clean_error(capsys, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(cli, "_open_scope", boom)
    code, out, err = run(["idn", "10.0.0.1"], capsys)
    assert code == 1
    assert "kaboom" in err
    assert "Traceback" not in err
