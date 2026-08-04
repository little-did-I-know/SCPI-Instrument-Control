"""Structured exception fields (typed-instrument-api Task 1)."""

import pytest

from scpi_control import exceptions


class TestInvalidParameterError:
    def test_plain_string_construction_still_works(self):
        err = exceptions.InvalidParameterError("bad thing")
        assert str(err) == "bad thing"
        assert err.parameter is None and err.valid_options is None

    def test_is_a_valueerror_and_a_siglenterror(self):
        # _to_wire and the PSU tracking setter used to raise bare ValueError;
        # the dual base keeps `except ValueError` callers working.
        err = exceptions.InvalidParameterError("x")
        assert isinstance(err, ValueError)
        assert isinstance(err, exceptions.SiglentError)

    def test_auto_built_message_names_parameter_value_and_options(self):
        err = exceptions.InvalidParameterError(
            parameter="trigger slope", value="POSITIVE",
            valid_options=["NEG", "POS", "WINDOW"], dialect="modern", model="SDS824X HD",
        )
        msg = str(err)
        assert "trigger slope" in msg and "'POSITIVE'" in msg
        assert "NEG, POS, WINDOW" in msg
        assert "modern" in msg and "SDS824X HD" in msg
        assert err.valid_options == ["NEG", "POS", "WINDOW"]

    def test_auto_built_message_omits_absent_context(self):
        err = exceptions.InvalidParameterError(parameter="coupling", value="XX", valid_options=["AC", "DC"])
        assert "dialect" not in str(err) and "None" not in str(err)

    def test_explicit_message_wins_but_fields_still_stored(self):
        err = exceptions.InvalidParameterError("custom", parameter="p", value="v")
        assert str(err) == "custom" and err.parameter == "p"


class TestCommandError:
    def test_plain_construction_unchanged(self):
        err = exceptions.CommandError("boom")
        assert str(err) == "boom" and err.command is None

    def test_fields_stored(self):
        err = exceptions.CommandError("boom", command=":TRIGger:MODE AUTO", dialect="modern",
                                      model="SDS824X HD", instrument_error='-224,"Illegal parameter value"')
        assert err.command == ":TRIGger:MODE AUTO"
        assert err.instrument_error == '-224,"Illegal parameter value"'

    def test_measurement_unavailable_subclass_unaffected(self):
        err = exceptions.MeasurementUnavailableError("****")
        assert isinstance(err, exceptions.CommandError) and str(err) == "****"


class TestCommandErrorContextAdoption:
    def test_psu_parse_failure_names_the_command(self):
        from unittest.mock import Mock

        from scpi_control.power_supply_output import PowerSupplyOutput
        from scpi_control.psu_models import OutputSpec

        psu = Mock()
        psu._get_command.return_value = "MEASure:VOLTage? CH1"
        psu.query.return_value = "garbage!"
        output = PowerSupplyOutput(psu, OutputSpec(1, 30.0, 3.0, 90.0, 0.001, 0.001))
        with pytest.raises(exceptions.CommandError) as exc_info:
            output.measure_voltage()
        assert exc_info.value.command == "MEASure:VOLTage? CH1"

    def test_socket_non_ascii_write_names_the_command(self):
        from scpi_control.connection.socket import SocketConnection

        conn = SocketConnection("192.0.2.1", 5025, 1.0)
        conn._connected = True   # reach the encode step without I/O
        conn._socket = object()
        with pytest.raises(exceptions.CommandError) as exc_info:
            conn.write("IDNé?")
        assert exc_info.value.command == "IDNé?"
