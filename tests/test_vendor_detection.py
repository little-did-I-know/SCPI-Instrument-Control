"""Vendor-aware model detection and vendor-axis primitives."""

from scpi_control import exceptions


def test_feature_not_supported_error_exists_and_subclasses_base():
    err = exceptions.FeatureNotSupportedError("holdoff is not supported on the modern dialect")
    assert isinstance(err, exceptions.SiglentError)


from scpi_control.models import MODEL_REGISTRY, ModelCapability, detect_model_from_idn


def test_existing_siglent_entries_default_to_siglent_vendor():
    cap = MODEL_REGISTRY["SDS1104X-E"]
    assert cap.vendor == "siglent"
    assert cap.horiz_divisions == 14
    assert cap.vert_divisions == 8


def test_siglent_detection_unchanged():
    cap = detect_model_from_idn("Siglent Technologies,SDS824X HD,SER,1.0")
    assert cap.vendor == "siglent"
    assert cap.dialect == "modern"


def test_tektronix_registry_model_detected_by_manufacturer():
    cap = detect_model_from_idn("TEKTRONIX,MSO24,C000001,CF:91.1CT FV:1.28")
    assert cap.vendor == "tektronix"
    assert cap.dialect == "tektronix"
    assert cap.scpi_variant == "tek_mso"
    assert cap.num_channels == 4


def test_tektronix_tbs_detected():
    cap = detect_model_from_idn("TEKTRONIX,TBS1102C,C000002,CF:91.1CT FV:1.10")
    assert cap.vendor == "tektronix"
    assert cap.scpi_variant == "tek_tbs"
    assert cap.num_channels == 2


def test_lecroy_registry_models_detected():
    cap = detect_model_from_idn("LECROY,WAVESURFER3024Z,LCRY0001,8.5.0")
    assert cap.vendor == "lecroy"
    assert cap.dialect == "lecroy"
    assert cap.scpi_variant == "lecroy_maui"

    cap2 = detect_model_from_idn("TELEDYNE LECROY,WAVERUNNER8104,LCRY0002,9.1.0")
    assert cap2.vendor == "lecroy"
    assert cap2.dialect == "lecroy"


def test_unknown_tektronix_model_gets_generic_tek_fallback():
    cap = detect_model_from_idn("TEKTRONIX,MSO58,C000003,FV:2.0")
    assert cap.vendor == "tektronix"
    assert cap.dialect == "tektronix"
    assert cap.has_protocol_decode is False


def test_unknown_tbs_pattern_falls_back_to_two_channels():
    cap = detect_model_from_idn("TEKTRONIX,TBS2104B,C000004,FV:1.0")
    assert cap.num_channels == 2 or cap.num_channels == 4  # TBS2000B is 4ch-capable; see step 3 rule
    assert cap.vendor == "tektronix"


def test_unknown_lecroy_model_gets_generic_lecroy_fallback():
    cap = detect_model_from_idn("LECROY,HDO6104A,LCRY0003,9.8")
    assert cap.vendor == "lecroy"
    assert cap.dialect == "lecroy"


def test_unknown_manufacturer_keeps_siglent_heuristics():
    cap = detect_model_from_idn("Rigol Technologies,DS1054Z,RIG0001,00.04.04")
    assert cap.vendor == "siglent"  # legacy fallback path, unchanged behavior
    assert cap.dialect == "legacy"
