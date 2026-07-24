"""One-shot migration of pre-5.0 pickled reference files."""

import json
import logging
from pathlib import Path

import numpy as np

from scpi_control.reference_waveform import ReferenceWaveform
from scpi_control.server.__main__ import main
from scpi_control.server.migrate import migrate_references


def _write_legacy(path, name):
    np.savez_compressed(path, time=np.arange(4, dtype=float), voltage=np.zeros(4), metadata={"name": name, "channel": 1})


def test_legacy_file_is_converted(tmp_path):
    _write_legacy(tmp_path / "ref_old.npz", "old")
    result = migrate_references(str(tmp_path))
    assert result == {"converted": 1, "skipped": 0, "failed": 0}
    with np.load(tmp_path / "ref_old.npz", allow_pickle=False) as data:
        assert "metadata" not in data.files
        assert json.loads(str(data["meta_json"]))["name"] == "old"


def test_converted_file_loads_through_the_normal_path(tmp_path):
    _write_legacy(tmp_path / "ref_old.npz", "old")
    migrate_references(str(tmp_path))
    loaded = ReferenceWaveform(str(tmp_path)).load_reference("old")
    assert loaded is not None
    assert loaded["metadata"]["name"] == "old"
    assert list(loaded["voltage"]) == [0.0, 0.0, 0.0, 0.0]


def test_already_migrated_files_are_skipped(tmp_path):
    target = tmp_path / "ref_old.npz"
    _write_legacy(target, "old")
    migrate_references(str(tmp_path))

    # Prove the second pass is a genuine no-op, not merely a clean exit: the
    # file must be byte-for-byte and mtime identical after the "skip".
    before_bytes = target.read_bytes()
    before_mtime = target.stat().st_mtime_ns

    result = migrate_references(str(tmp_path))

    assert result == {"converted": 0, "skipped": 1, "failed": 0}
    assert target.read_bytes() == before_bytes
    assert target.stat().st_mtime_ns == before_mtime


def test_unreadable_file_is_counted_not_fatal(tmp_path):
    broken = tmp_path / "ref_broken.npz"
    broken.write_bytes(b"not an npz")
    result = migrate_references(str(tmp_path))
    assert result == {"converted": 0, "skipped": 0, "failed": 1}
    # The broken file itself must survive untouched -- "not fatal" means the
    # run continues, not that the unreadable file gets silently replaced.
    assert broken.read_bytes() == b"not an npz"


def test_counts_sum_to_files_examined(tmp_path):
    _write_legacy(tmp_path / "ref_legacy.npz", "legacy")
    already = tmp_path / "ref_new.npz"
    np.savez_compressed(already, time=np.arange(4, dtype=float), voltage=np.zeros(4), meta_json=json.dumps({"name": "new"}))
    (tmp_path / "ref_broken.npz").write_bytes(b"garbage")

    result = migrate_references(str(tmp_path))

    assert result == {"converted": 1, "skipped": 1, "failed": 1}
    assert sum(result.values()) == 3


def test_failed_conversion_leaves_original_file_intact(tmp_path, monkeypatch):
    storage = tmp_path / "refs"
    storage.mkdir()
    target = storage / "ref_old.npz"
    _write_legacy(target, "old")
    before_bytes = target.read_bytes()

    def _boom(file, *args, **kwargs):
        # A real partial write leaves garbage bytes sitting wherever
        # savez_compressed was writing before it died -- reproduce that
        # here. A naive implementation that writes straight over the
        # original file (no temp file, no os.replace) would corrupt
        # ref_old.npz right here and fail the assertions below; only the
        # atomic temp-file-then-swap approach leaves the original untouched,
        # because the garbage lands in a temp file that then gets unlinked.
        if hasattr(file, "write"):
            file.write(b"garbage from a partial write")
            file.flush()
        else:
            Path(file).write_bytes(b"garbage from a partial write")
        raise OSError("disk full")

    monkeypatch.setattr("scpi_control.server.migrate.np.savez_compressed", _boom)

    result = migrate_references(str(storage))

    assert result == {"converted": 0, "skipped": 0, "failed": 1}
    # A conversion that dies partway through must not leave a truncated
    # replacement -- the original, still-readable-as-legacy file must remain.
    assert target.read_bytes() == before_bytes
    # Byte-identity alone would also hold for a file that was never readable
    # in the first place, so prove the survivor is still a loadable archive.
    with np.load(target, allow_pickle=True) as survivor:
        assert survivor["metadata"].item()["name"] == "old"
    assert target.exists()
    # No leftover temp file should linger in the storage directory either.
    assert sorted(p.name for p in storage.iterdir()) == ["ref_old.npz"]


def test_orphaned_temp_file_is_ignored_by_the_scan(tmp_path):
    # A leftover *.npz.tmp from a killed run has none of the structure
    # _build_payload expects. If the scan's "*.npz" glob matched it, it
    # would blow up in np.load and get counted as failed. It must simply
    # never be examined by the converted/skipped/failed loop at all.
    orphan = tmp_path / "ref_old.abcd1234.npz.tmp"
    orphan.write_bytes(b"partial write from a process that got SIGKILLed")
    _write_legacy(tmp_path / "ref_old.npz", "old")

    result = migrate_references(str(tmp_path))

    assert result == {"converted": 1, "skipped": 0, "failed": 0}


def test_stale_temp_file_is_cleaned_up_and_logged(tmp_path, caplog):
    # Simulates the process being killed between the temp-file write and
    # os.replace in a *previous* run: the orphan must be swept up (and
    # mentioned in the log) at the start of the *next* run, or it litters
    # the directory forever.
    orphan = tmp_path / "ref_old.abcd1234.npz.tmp"
    orphan.write_bytes(b"partial write from a process that got SIGKILLed")

    with caplog.at_level(logging.INFO, logger="scpi_control.server.migrate"):
        result = migrate_references(str(tmp_path))

    assert not orphan.exists()
    # A stale temp file is not a reference file -- it must not be counted
    # as converted, skipped, or failed.
    assert result == {"converted": 0, "skipped": 0, "failed": 0}
    assert orphan.name in caplog.text


def test_cli_references_migrate_dispatches_and_prints_summary(tmp_path, capsys):
    _write_legacy(tmp_path / "ref_old.npz", "old")

    main(["references", "migrate", "--dir", str(tmp_path)])

    printed = capsys.readouterr().out
    assert "converted 1" in printed
    assert "skipped 0" in printed
    assert "failed 0" in printed
    with np.load(tmp_path / "ref_old.npz", allow_pickle=False) as data:
        assert "meta_json" in data.files


def test_cli_references_migrate_defaults_to_config_dir_references_subdir(tmp_path, capsys):
    # No --dir given: must resolve under DEFAULT_CONFIG_DIR (patched to the
    # fake home by the autouse _no_real_home fixture), never the real home.
    default_refs = tmp_path / "fake-home" / ".siglent" / "references"
    default_refs.mkdir(parents=True)
    _write_legacy(default_refs / "ref_old.npz", "old")

    main(["references", "migrate"])

    printed = capsys.readouterr().out
    assert "converted 1" in printed
    with np.load(default_refs / "ref_old.npz", allow_pickle=False) as data:
        assert "meta_json" in data.files
