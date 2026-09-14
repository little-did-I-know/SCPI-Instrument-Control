"""Pilot coverage: Trigger.source warns instead of silently coercing.

Covers the two SDS824X HD quirks encoded in ModelCapability
(unreliable_trigger_sources, warns_on_disabled_trigger_channel) and proves
the warning path is a no-op for models/test-doubles that don't carry a
real ModelCapability -- the existing dual-dialect trigger test suites use
plain unittest.mock.Mock() scopes (see tests/dialect_helpers.py), which
must keep passing unchanged.
"""

import dataclasses
import logging
from unittest.mock import Mock

from scpi_control.models import MODEL_REGISTRY
from scpi_control.trigger import Trigger
from tests.dialect_helpers import make_dialect_scope


def _sds824x_hd_scope(channel_enabled: bool = True):
    scope = make_dialect_scope("modern")
    scope.model_capability = MODEL_REGISTRY["SDS824X HD"]
    scope.get_channel = Mock(return_value=Mock(enabled=channel_enabled))
    return scope


class TestUnreliableSourceWarnings:
    def test_setting_ex_warns(self, caplog):
        scope = _sds824x_hd_scope()
        trigger = Trigger(scope)
        with caplog.at_level(logging.WARNING):
            trigger.source = "EX"
        assert any("EX" in r.message and "SDS824X HD" in r.message for r in caplog.records)
        # The write is unchanged regardless of the warning.
        scope.write.assert_called_once_with(":TRIGger:EDGE:SOURce EX")

    def test_setting_ex5_warns(self, caplog):
        scope = _sds824x_hd_scope()
        trigger = Trigger(scope)
        with caplog.at_level(logging.WARNING):
            trigger.source = "EX5"
        assert any("EX5" in r.message for r in caplog.records)

    def test_setting_line_does_not_warn(self, caplog):
        scope = _sds824x_hd_scope()
        trigger = Trigger(scope)
        with caplog.at_level(logging.WARNING):
            trigger.source = "LINE"
        assert caplog.records == []


class TestDisabledChannelWarnings:
    def test_disabled_channel_warns(self, caplog):
        scope = _sds824x_hd_scope(channel_enabled=False)
        trigger = Trigger(scope)
        with caplog.at_level(logging.WARNING):
            trigger.source = "C2"
        assert any("C2" in r.message and "disabled" in r.message for r in caplog.records)
        scope.get_channel.assert_called_once_with(2)

    def test_enabled_channel_does_not_warn(self, caplog):
        scope = _sds824x_hd_scope(channel_enabled=True)
        trigger = Trigger(scope)
        with caplog.at_level(logging.WARNING):
            trigger.source = "C2"
        assert caplog.records == []


class TestNonexistentChannelWarnings:
    def test_channel_beyond_model_capacity_warns(self, caplog):
        # SDS1202X-E is a real 2-channel legacy-dialect model with neither
        # quirk flag set -- proves the existence check fires independently
        # of warns_on_disabled_trigger_channel.
        scope = make_dialect_scope("legacy")
        scope.model_capability = MODEL_REGISTRY["SDS1202X-E"]
        scope.query.return_value = "EDGE,SR,C1"  # current trigger type, preserved by the setter
        trigger = Trigger(scope)
        with caplog.at_level(logging.WARNING):
            trigger.source = "C3"
        assert any("C3" in r.message and "2 channel" in r.message for r in caplog.records)
        scope.write.assert_called_once()

    def test_channel_within_model_capacity_does_not_warn(self, caplog):
        scope = make_dialect_scope("legacy")
        scope.model_capability = MODEL_REGISTRY["SDS1202X-E"]
        scope.query.return_value = "EDGE,SR,C1"  # current trigger type, preserved by the setter
        trigger = Trigger(scope)
        with caplog.at_level(logging.WARNING):
            trigger.source = "C2"
        assert caplog.records == []

    def test_flagged_model_with_fewer_channels_still_warns_on_nonexistent_channel(self, caplog):
        # Regression test for the latent gap this was written to close: a
        # future narrower model that also sets warns_on_disabled_trigger_channel
        # must not treat a nonexistent channel as "not disabled" and stay
        # silent. The existence check must fire before the disabled check
        # even gets a chance to see get_channel() return None.
        narrower = dataclasses.replace(MODEL_REGISTRY["SDS824X HD"], num_channels=2)
        scope = make_dialect_scope("modern")
        scope.model_capability = narrower
        scope.get_channel = Mock(return_value=None)
        trigger = Trigger(scope)
        with caplog.at_level(logging.WARNING):
            trigger.source = "C3"
        assert any("C3" in r.message and "does not exist" in r.message for r in caplog.records)
        scope.get_channel.assert_not_called()


class TestDisabledChannelWarningPerformance:
    def test_disabled_channel_check_skipped_when_warning_disabled(self, caplog):
        # Channel.enabled issues a live query; suppressing this logger's
        # warnings must also skip the round-trip, not just the message.
        scope = _sds824x_hd_scope(channel_enabled=False)
        trigger = Trigger(scope)
        with caplog.at_level(logging.ERROR, logger="scpi_control.trigger"):
            trigger.source = "C2"
        scope.get_channel.assert_not_called()
        assert caplog.records == []


class TestNoFlagsNoWarning:
    def test_model_without_flags_set_does_not_warn(self, caplog):
        # SDS804X HD has never been measured for this quirk -- flags default off.
        scope = make_dialect_scope("modern")
        scope.model_capability = MODEL_REGISTRY["SDS804X HD"]
        trigger = Trigger(scope)
        with caplog.at_level(logging.WARNING):
            trigger.source = "EX"
        assert caplog.records == []

    def test_flags_cleared_on_copy_does_not_warn(self, caplog):
        # Same underlying model, flags explicitly cleared -- proves the
        # warning is driven by the flags, not by the model name.
        cleared = dataclasses.replace(
            MODEL_REGISTRY["SDS824X HD"],
            unreliable_trigger_sources=frozenset(),
            warns_on_disabled_trigger_channel=False,
        )
        scope = make_dialect_scope("modern")
        scope.model_capability = cleared
        scope.get_channel = Mock(return_value=Mock(enabled=False))
        trigger = Trigger(scope)
        with caplog.at_level(logging.WARNING):
            trigger.source = "EX"
            trigger.source = "C2"
        assert caplog.records == []

    def test_plain_mock_model_capability_does_not_warn_or_crash(self, caplog):
        # tests/dialect_helpers.make_dialect_scope leaves model_capability as
        # a plain unittest.mock.Mock (only .num_channels is set). This must
        # not raise -- it's the exact shape used across the existing trigger
        # test suites (e.g. TestTriggerModernDialect in
        # tests/test_trigger_comprehensive.py).
        scope = make_dialect_scope("modern")
        trigger = Trigger(scope)
        with caplog.at_level(logging.WARNING):
            trigger.source = "EX"
            trigger.source = "C2"
        assert caplog.records == []
