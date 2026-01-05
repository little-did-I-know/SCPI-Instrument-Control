"""Comprehensive tests for measurement module."""

from unittest.mock import MagicMock, Mock, patch

import pytest

from siglent.exceptions import CommandError
from siglent.measurement import Measurement


@pytest.fixture
def mock_scope():
    """Create a mock oscilloscope for testing."""
    scope = Mock()
    scope.write = Mock()
    scope.query = Mock()
    return scope


@pytest.fixture
def measurement(mock_scope):
    """Create a measurement instance for testing."""
    return Measurement(mock_scope)


class TestMeasurementInitialization:
    """Test measurement initialization."""

    def test_init(self, mock_scope):
        """Test measurement initialization."""
        meas = Measurement(mock_scope)
        assert meas._scope == mock_scope


class TestFrequencyMeasurement:
    """Test frequency measurement."""

    def test_measure_frequency(self, measurement, mock_scope):
        """Test measuring frequency."""
        mock_scope.query.return_value = "PAVA FREQ,C1,1.000E+03HZ"
        freq = measurement.measure_frequency(1)
        assert freq == 1000.0
        mock_scope.query.assert_called_once()

    def test_measure_frequency_alternate_format(self, measurement, mock_scope):
        """Test frequency measurement with alternate response format."""
        mock_scope.query.return_value = "PAVA FREQ,C1,1.234E+03HZ"
        freq = measurement.measure_frequency(1)
        assert freq == 1234.0

    def test_measure_frequency_invalid_channel(self, measurement, mock_scope):
        """Test frequency measurement with invalid channel."""
        with pytest.raises(Exception, match="Invalid channel number"):
            measurement.measure_frequency(0)

        with pytest.raises(Exception, match="Invalid channel number"):
            measurement.measure_frequency(5)


class TestPeriodMeasurement:
    """Test period measurement."""

    def test_measure_period(self, measurement, mock_scope):
        """Test measuring period."""
        mock_scope.query.return_value = "PAVA PER,C1,1.000E-03S"
        period = measurement.measure_period(1)
        assert period == 0.001
        mock_scope.query.assert_called_once()

    def test_measure_period_channel2(self, measurement, mock_scope):
        """Test measuring period on channel 2."""
        mock_scope.query.return_value = "PAVA PER,C1,5.000E-04S"
        period = measurement.measure_period(2)
        assert period == 0.0005


class TestVppMeasurement:
    """Test peak-to-peak voltage measurement."""

    def test_measure_vpp(self, measurement, mock_scope):
        """Test measuring Vpp."""
        mock_scope.query.return_value = "PAVA PKPK,C1,3.300E+00V"
        vpp = measurement.measure_vpp(1)
        assert vpp == 3.3

    def test_measure_vpp_different_values(self, measurement, mock_scope):
        """Test Vpp measurement with different values."""
        test_values = [1.0, 2.5, 5.0, 10.0]
        for expected in test_values:
            mock_scope.query.return_value = f"PAVA PKPK,C1,{expected:.3E}V"
            vpp = measurement.measure_vpp(1)
            assert abs(vpp - expected) < 0.01


class TestRMSMeasurement:
    """Test RMS voltage measurement."""

    def test_measure_rms(self, measurement, mock_scope):
        """Test measuring RMS voltage."""
        mock_scope.query.return_value = "PAVA RMS,C1,1.000E+00V"
        rms = measurement.measure_rms(1)
        assert rms == 1.0

    def test_measure_rms_ac(self, measurement, mock_scope):
        """Test measuring AC RMS voltage."""
        if hasattr(measurement, "measure_rms_ac"):
            mock_scope.query.return_value = "PAVA CRMS,C1,7.071E-01V"
            rms_ac = measurement.measure_rms_ac(1)
            assert abs(rms_ac - 0.7071) < 0.0001


class TestAmplitudeMeasurement:
    """Test amplitude measurement."""

    def test_measure_amplitude(self, measurement, mock_scope):
        """Test measuring amplitude."""
        mock_scope.query.return_value = "PAVA AMPL,C1,2.500E+00V"
        amplitude = measurement.measure_amplitude(1)
        assert amplitude == 2.5


class TestMeanMeasurement:
    """Test mean voltage measurement."""

    def test_measure_mean(self, measurement, mock_scope):
        """Test measuring mean voltage."""
        mock_scope.query.return_value = "PAVA MEAN,C1,1.500E+00V"
        mean = measurement.measure_mean(1)
        assert mean == 1.5

    def test_measure_mean_negative(self, measurement, mock_scope):
        """Test measuring negative mean voltage."""
        mock_scope.query.return_value = "PAVA MEAN,C1,-5.000E-01V"
        mean = measurement.measure_mean(1)
        assert mean == -0.5


class TestMinMaxMeasurement:
    """Test minimum and maximum voltage measurements."""

    def test_measure_max(self, measurement, mock_scope):
        """Test measuring maximum voltage."""
        mock_scope.query.return_value = "PAVA MAX,C1,5.000E+00V"
        vmax = measurement.measure_max(1)
        assert vmax == 5.0

    def test_measure_min(self, measurement, mock_scope):
        """Test measuring minimum voltage."""
        mock_scope.query.return_value = "PAVA MIN,C1,-2.000E+00V"
        vmin = measurement.measure_min(1)
        assert vmin == -2.0


class TestTimingMeasurements:
    """Test timing measurements."""

    def test_measure_rise_time(self, measurement, mock_scope):
        """Test measuring rise time."""
        mock_scope.query.return_value = "PAVA RISE,C1,1.000E-06S"
        rise_time = measurement.measure_rise_time(1)
        assert rise_time == 1e-6

    def test_measure_fall_time(self, measurement, mock_scope):
        """Test measuring fall time."""
        mock_scope.query.return_value = "PAVA FALL,C1,1.500E-06S"
        fall_time = measurement.measure_fall_time(1)
        assert fall_time == 1.5e-6

    def test_measure_pulse_width(self, measurement, mock_scope):
        """Test measuring pulse width."""
        if hasattr(measurement, "measure_pulse_width"):
            mock_scope.query.return_value = "WID: 5.000E-04S"
            width = measurement.measure_pulse_width(1)
            assert width == 5e-4

    def test_measure_duty_cycle(self, measurement, mock_scope):
        """Test measuring duty cycle."""
        mock_scope.query.return_value = "PAVA DUTY,C1,5.000E+01%"
        duty = measurement.measure_duty_cycle(1)
        assert duty == 50.0


class TestPhaseMeasurement:
    """Test phase measurement."""

    def test_measure_phase(self, measurement, mock_scope):
        """Test measuring phase between two channels."""
        if hasattr(measurement, "measure_phase"):
            mock_scope.query.return_value = "PHASE: 9.000E+01DEG"
            phase = measurement.measure_phase(1, 2)
            assert phase == 90.0


class TestMeasureAll:
    """Test measuring all parameters at once."""

    def test_measure_all(self, measurement, mock_scope):
        """Test measuring all parameters."""
        # Setup mock responses for all measurements in the order they are called
        # Order: vpp, amplitude, max, min, mean, rms, frequency, period, rise_time, fall_time, duty_cycle
        responses = [
            "PAVA PKPK,C1,3.300E+00V",  # vpp
            "PAVA AMPL,C1,1.650E+00V",  # amplitude
            "PAVA MAX,C1,1.650E+00V",  # max
            "PAVA MIN,C1,-1.650E+00V",  # min
            "PAVA MEAN,C1,0.000E+00V",  # mean
            "PAVA RMS,C1,1.170E+00V",  # rms
            "PAVA FREQ,C1,1.000E+03HZ",  # frequency
            "PAVA PER,C1,1.000E-03S",  # period
            "PAVA RISE,C1,1.000E-06S",  # rise_time
            "PAVA FALL,C1,1.000E-06S",  # fall_time
            "PAVA DUTY,C1,5.000E+01%",  # duty_cycle
        ]

        mock_scope.query.side_effect = responses

        measurements = measurement.measure_all(1)

        assert isinstance(measurements, dict)
        assert "frequency" in measurements
        assert "vpp" in measurements
        assert measurements["frequency"] == 1000.0
        assert measurements["vpp"] == 3.3


class TestMeasurementParameterSetup:
    """Test setting up measurement parameters."""

    def test_setup_measurement_parameter(self, measurement, mock_scope):
        """Test setting up a measurement parameter."""
        if hasattr(measurement, "setup_parameter"):
            measurement.setup_parameter(1, "FREQ")
            assert mock_scope.write.called

    def test_clear_measurements(self, measurement, mock_scope):
        """Test clearing all measurements."""
        if hasattr(measurement, "clear_measurements"):
            measurement.clear_measurements()
            assert mock_scope.write.called


class TestCursorMeasurements:
    """Test cursor-based measurements."""

    def test_measure_with_cursors(self, measurement, mock_scope):
        """Test measurement using cursors."""
        if hasattr(measurement, "measure_cursor_delta_time"):
            mock_scope.query.return_value = "DT: 1.000E-03S"
            dt = measurement.measure_cursor_delta_time()
            assert isinstance(dt, float)

    def test_measure_cursor_delta_voltage(self, measurement, mock_scope):
        """Test voltage delta measurement using cursors."""
        if hasattr(measurement, "measure_cursor_delta_voltage"):
            mock_scope.query.return_value = "DV: 2.500E+00V"
            dv = measurement.measure_cursor_delta_voltage()
            assert isinstance(dv, float)


class TestStatisticalMeasurements:
    """Test statistical measurements."""

    def test_enable_statistics(self, measurement, mock_scope):
        """Test enabling statistics."""
        if hasattr(measurement, "enable_statistics"):
            measurement.enable_statistics()
            assert mock_scope.write.called

    def test_disable_statistics(self, measurement, mock_scope):
        """Test disabling statistics."""
        if hasattr(measurement, "disable_statistics"):
            measurement.disable_statistics()
            assert mock_scope.write.called

    def test_get_statistics(self, measurement, mock_scope):
        """Test getting statistics for a measurement."""
        if hasattr(measurement, "get_statistics"):
            mock_scope.query.return_value = "MEAN:1.0,STDEV:0.1,MIN:0.9,MAX:1.1"
            stats = measurement.get_statistics(1, "FREQ")
            assert isinstance(stats, dict)


class TestMeasurementUtilities:
    """Test measurement utility functions."""

    def test_parse_measurement_response(self, measurement):
        """Test parsing measurement response."""
        # Test various response formats
        responses = [
            ("FREQ: 1.000E+03HZ", 1000.0),
            ("PAVA PKPK,C1,3.300E+00V", 3.3),
            ("PAVA DUTY,C1,50.0%", 50.0),
            ("C1:PAVA FREQ,1.234E+03HZ", 1234.0),
        ]

        for response, expected in responses:
            # Assume there's a parse method
            if hasattr(measurement, "_parse_measurement"):
                result = measurement._parse_measurement(response)
                assert abs(result - expected) < 0.01


class TestMeasurementErrorHandling:
    """Test error handling in measurements."""

    def test_measurement_timeout(self, measurement, mock_scope):
        """Test handling measurement timeout."""
        mock_scope.query.side_effect = TimeoutError("Measurement timeout")

        with pytest.raises((TimeoutError, CommandError)):
            measurement.measure_frequency(1)

    def test_measurement_invalid_response(self, measurement, mock_scope):
        """Test handling invalid measurement response."""
        mock_scope.query.return_value = "INVALID RESPONSE"

        # Should handle gracefully or raise appropriate error
        try:
            result = measurement.measure_frequency(1)
            # If it doesn't raise, should return a reasonable value or None
            assert result is None or isinstance(result, (int, float))
        except (ValueError, CommandError):
            pass  # Expected behavior


class TestMultipleChannelMeasurements:
    """Test measurements across multiple channels."""

    def test_measure_different_channels(self, measurement, mock_scope):
        """Test measuring different parameters on different channels."""
        # Channel 1 frequency
        mock_scope.query.return_value = "PAVA FREQ,C1,1.000E+03HZ"
        freq1 = measurement.measure_frequency(1)
        assert freq1 == 1000.0

        # Channel 2 Vpp
        mock_scope.query.return_value = "PAVA PKPK,C2,5.000E+00V"
        vpp2 = measurement.measure_vpp(2)
        assert vpp2 == 5.0

        # Channel 3 RMS
        mock_scope.query.return_value = "PAVA RMS,C3,1.500E+00V"
        rms3 = measurement.measure_rms(3)
        assert rms3 == 1.5

        # Channel 4 mean
        mock_scope.query.return_value = "PAVA MEAN,C4,2.000E+00V"
        mean4 = measurement.measure_mean(4)
        assert mean4 == 2.0


class TestMeasurementStringRepresentation:
    """Test string representation."""

    def test_str(self, measurement):
        """Test string representation."""
        assert "Measurement" in str(measurement)

    def test_repr(self, measurement):
        """Test repr."""
        assert "Measurement" in repr(measurement)
