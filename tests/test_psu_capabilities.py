"""PSU capabilities and tracking vocabulary (typed-instrument-api Task 7)."""

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
