"""Tests for scpi_control.models.ModelCapability quirk-flag defaults."""

from scpi_control.models import MODEL_REGISTRY, ModelCapability


class TestTriggerQuirkFlags:
    """Trigger-source coercion capability flags (pilot: SDS824X HD only)."""

    def test_sds824x_hd_flags_known_unreliable_sources(self):
        cap = MODEL_REGISTRY["SDS824X HD"]
        assert cap.unreliable_trigger_sources == frozenset({"EX", "EX5"})
        assert cap.warns_on_disabled_trigger_channel is True

    def test_unmeasured_model_keeps_default_flags(self):
        # SDS804X HD has not been measured for this quirk -- must not
        # inherit SDS824X HD's flags or invent a claim about its hardware.
        cap = MODEL_REGISTRY["SDS804X HD"]
        assert cap.unreliable_trigger_sources == frozenset()
        assert cap.warns_on_disabled_trigger_channel is False

    def test_flags_default_to_unflagged_for_a_fresh_capability(self):
        cap = ModelCapability(
            model_name="FAKE",
            series="Test",
            num_channels=4,
            max_sample_rate=1.0,
            memory_depth=1000,
            bandwidth_mhz=100,
            has_math_channels=False,
            has_fft=False,
            has_protocol_decode=False,
            supported_decode_types=[],
            scpi_variant="standard",
        )
        assert cap.unreliable_trigger_sources == frozenset()
        assert cap.warns_on_disabled_trigger_channel is False
