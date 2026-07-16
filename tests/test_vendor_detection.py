"""Vendor-aware model detection and vendor-axis primitives."""

import pytest

from scpi_control import exceptions


def test_feature_not_supported_error_exists_and_subclasses_base():
    err = exceptions.FeatureNotSupportedError("holdoff is not supported on the modern dialect")
    assert isinstance(err, exceptions.SiglentError)
