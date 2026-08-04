"""FeatureNotSupportedError is catchable both ways (capability-honesty Task 1)."""

import pytest

from scpi_control import exceptions


def test_is_a_siglent_error_and_a_not_implemented_error():
    err = exceptions.FeatureNotSupportedError("no such feature")
    assert isinstance(err, exceptions.SiglentError)
    assert isinstance(err, NotImplementedError)
    assert str(err) == "no such feature"


def test_existing_handlers_keep_working():
    # The PSU gates used to raise bare NotImplementedError. Callers written
    # against that must keep working -- this is why the class is dual-based.
    with pytest.raises(NotImplementedError):
        raise exceptions.FeatureNotSupportedError("tracking not supported")


def test_still_catchable_as_the_library_base():
    with pytest.raises(exceptions.SiglentError):
        raise exceptions.FeatureNotSupportedError("x")
