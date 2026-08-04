"""PSU capabilities and tracking vocabulary (typed-instrument-api Task 7)."""

import dataclasses
import pytest

from scpi_control import exceptions
from scpi_control.power_supply import PowerSupply
from scpi_control.psu_models import create_generic_psu_capability, detect_psu_from_idn
from scpi_control.vocabulary import TrackingMode


class TestGenericCapabilityHonesty:
    def test_unknown_model_no_longer_advertises_protection(self):
        # psu_models.py shipped has_ovp=True/has_ocp=True for unrecognized
        # models -- re-opening the exact uncitable VOLT:PROT path the wave-1
        # High-3 gate closed for the SPD registry (audit H18 class).
        caps = detect_psu_from_idn("Acme Instruments,PS-1000,SN1,1.0")
        assert caps.has_ovp is False
        assert caps.has_ocp is False
        assert caps.scpi_variant == "generic"

    def test_create_generic_directly(self):
        caps = create_generic_psu_capability("Acme,PS-1000,SN1,1.0")
        assert caps.has_ovp is False and caps.has_ocp is False

    def test_registry_models_unchanged(self):
        caps = detect_psu_from_idn("Siglent Technologies,SPD3303X,SPD3XABC,V1.01")
        assert caps.model_name == "SPD3303X" and caps.has_timer is True


class TestCapabilitiesProperty:
    def test_raises_before_connect(self):
        psu = PowerSupply("192.0.2.1")  # never connected; no I/O happens
        with pytest.raises(exceptions.SiglentConnectionError):
            psu.capabilities

    def test_returns_model_capability_when_connected(self):
        psu = PowerSupply("192.0.2.1")
        psu.model_capability = detect_psu_from_idn("Siglent Technologies,SPD3303X,SPD3XABC,V1.01")
        assert psu.capabilities is psu.model_capability


class TestTrackingVocabulary:
    def _psu_with_tracking(self):
        psu = PowerSupply("192.0.2.1")
        psu.model_capability = detect_psu_from_idn("Siglent Technologies,SPD3303X,SPD3XABC,V1.01")
        from scpi_control.psu_scpi_commands import PSUSCPICommandSet

        psu._scpi_commands = PSUSCPICommandSet("siglent_spd")
        return psu

    def test_enum_accepted_and_numeric_wire_form_kept(self, monkeypatch):
        psu = self._psu_with_tracking()
        sent = []
        monkeypatch.setattr(psu, "write", sent.append)
        psu.tracking_mode = TrackingMode.SERIES
        assert sent == ["OUTP:TRACK 1"]  # QS0503X-E01B p.40: numeric on the wire

    def test_invalid_mode_structured_and_still_a_valueerror(self, monkeypatch):
        psu = self._psu_with_tracking()
        monkeypatch.setattr(psu, "write", lambda cmd: pytest.fail("must not reach the wire"))
        with pytest.raises(ValueError) as exc_info:  # old contract preserved
            psu.tracking_mode = "SIDEWAYS"
        assert isinstance(exc_info.value, exceptions.InvalidParameterError)
        assert exc_info.value.parameter == "tracking mode"
        assert exc_info.value.model == "SPD3303X"


class TestOutputCapabilityFlags:
    def test_flags_default_to_true_so_existing_models_are_unchanged(self):
        from scpi_control.psu_models import OutputSpec

        spec = OutputSpec(1, 30.0, 3.0, 90.0, 0.001, 0.001)
        assert spec.programmable and spec.measurable and spec.switchable
        assert spec.state_readable and spec.supports_timer and spec.supports_waveform

    def test_spd3303x_ch3_is_switchable_but_nothing_else(self):
        from scpi_control.psu_models import PSU_MODEL_REGISTRY

        # QS0503X-E01B: OUTPut {CH1|CH2|CH3} p.40 -- CH3 IS switchable.
        # VOLTage/CURRent p.39, MEASure p.38, TIMEr p.41, OUTPut:WAVE p.40 are
        # all CH1|CH2 only, and p.42's status bitmap has no CH3 state bit.
        for model in ("SPD3303X", "SPD3303X-E"):
            ch3 = PSU_MODEL_REGISTRY[model].output_specs[2]
            assert ch3.output_num == 3
            assert ch3.switchable is True
            assert ch3.programmable is False
            assert ch3.measurable is False
            assert ch3.state_readable is False
            assert ch3.supports_timer is False
            assert ch3.supports_waveform is False

    def test_ch1_and_ch2_keep_every_capability(self):
        from scpi_control.psu_models import PSU_MODEL_REGISTRY

        for model in ("SPD3303X", "SPD3303X-E"):
            for index in (0, 1):
                spec = PSU_MODEL_REGISTRY[model].output_specs[index]
                assert spec.programmable and spec.measurable and spec.switchable
                assert spec.state_readable and spec.supports_timer and spec.supports_waveform


class TestFrozenCapabilities:
    def test_output_spec_rejects_mutation(self):
        from scpi_control.psu_models import PSU_MODEL_REGISTRY

        # psu.capabilities hands back the shared registry singleton; a caller
        # flipping a flag would re-enable the silent no-op process-wide.
        with pytest.raises(dataclasses.FrozenInstanceError):
            PSU_MODEL_REGISTRY["SPD3303X"].output_specs[2].programmable = True

    def test_psu_capability_rejects_mutation(self):
        from scpi_control.psu_models import PSU_MODEL_REGISTRY

        with pytest.raises(dataclasses.FrozenInstanceError):
            PSU_MODEL_REGISTRY["SPD3303X"].has_ovp = True


def test_no_model_other_than_spd3303x_ch3_restricts_any_output():
    """Default-True flags must not have leaked a restriction into another model.

    This is the most likely way this change goes wrong: a flag defaulting the
    wrong way, or a copy-paste into the wrong registry entry, would silently
    start raising for models nobody meant to touch.
    """
    from scpi_control.psu_models import PSU_MODEL_REGISTRY

    for model_name, capability in PSU_MODEL_REGISTRY.items():
        for spec in capability.output_specs:
            restricted = not all(
                [
                    spec.programmable,
                    spec.measurable,
                    spec.switchable,
                    spec.state_readable,
                    spec.supports_timer,
                    spec.supports_waveform,
                ]
            )
            expected = model_name in ("SPD3303X", "SPD3303X-E") and spec.output_num == 3
            assert restricted == expected, f"{model_name} output {spec.output_num} restriction changed unexpectedly"


def test_generic_fallback_output_is_unrestricted():
    from scpi_control.psu_models import create_generic_psu_capability

    capability = create_generic_psu_capability("Acme,PSU-1,SN,1.0")
    spec = capability.output_specs[0]
    assert spec.programmable and spec.measurable and spec.switchable
    assert spec.state_readable and spec.supports_timer and spec.supports_waveform
