"""The base URL the gateway records so `invite` can print a clickable link."""

from pathlib import Path

from scpi_control.server.gateway_url import read_base_url, write_base_url


def test_a_concrete_host_is_used_verbatim(tmp_path):
    url = write_base_url(Path(tmp_path), "192.168.1.50", 8765)
    assert url == "http://192.168.1.50:8765/"
    assert read_base_url(Path(tmp_path)) == url


def test_a_wildcard_host_resolves_to_a_reachable_address(tmp_path):
    # Printing http://0.0.0.0:8765/ would hand the recipient a link that
    # cannot be opened, which is the exact failure this feature removes.
    url = write_base_url(Path(tmp_path), "0.0.0.0", 8765)
    assert "0.0.0.0" not in url
    assert url.startswith("http://") and url.endswith(":8765/")


def test_loopback_is_kept_as_loopback(tmp_path):
    # The default bind really is local-only; rewriting it to a LAN address
    # would advertise access that does not exist.
    assert write_base_url(Path(tmp_path), "127.0.0.1", 8765) == "http://127.0.0.1:8765/"


def test_reading_before_any_gateway_started_returns_none(tmp_path):
    assert read_base_url(Path(tmp_path)) is None


def test_a_corrupt_url_record_reads_as_none(tmp_path):
    # Unlike the token and invitation stores, this file holds no security
    # state -- it is a convenience. A damaged one must degrade to "I don't
    # know the URL", not stop the admin from issuing an invitation.
    (tmp_path / "gateway.json").write_text("{ not json")
    assert read_base_url(Path(tmp_path)) is None
