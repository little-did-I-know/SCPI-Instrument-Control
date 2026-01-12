"""SCPI command sets for Data Acquisition system control.

Provides generic SCPI-99 commands for DAQ systems,
with Keysight-specific command overrides for 34970A/DAQ970A series.
"""

import logging
from typing import Dict, List, Union

logger = logging.getLogger(__name__)


def format_channel_list(channels: Union[int, List[int], str]) -> str:
    """Format channel list for SCPI commands.

    Args:
        channels: Channel number(s) - can be:
                 - Single int: 101
                 - List of ints: [101, 102, 103]
                 - String (already formatted): "(@101:103)"

    Returns:
        Formatted channel string like "(@101,102,103)" or "(@101:110)"

    Examples:
        >>> format_channel_list(101)
        '(@101)'
        >>> format_channel_list([101, 102, 103])
        '(@101,102,103)'
        >>> format_channel_list("(@101:110)")
        '(@101:110)'
    """
    if isinstance(channels, str):
        # Already formatted
        if channels.startswith("(@"):
            return channels
        return f"(@{channels})"
    elif isinstance(channels, int):
        return f"(@{channels})"
    elif isinstance(channels, (list, tuple)):
        return f"(@{','.join(str(ch) for ch in channels)})"
    else:
        raise ValueError(f"Invalid channel format: {channels}")


class DAQSCPICommandSet:
    """SCPI command abstraction for Data Acquisition systems.

    Supports generic SCPI-99 commands with model-specific overrides for
    known manufacturers (e.g., Keysight 34970A/DAQ970A series).
    """

    # Generic SCPI-99 commands (standard compliant)
    GENERIC_COMMANDS: Dict[str, str] = {
        # System commands (IEEE 488.2)
        "identify": "*IDN?",
        "reset": "*RST",
        "clear_status": "*CLS",
        "get_error": "SYST:ERR?",
        "operation_complete": "*OPC?",
        # Configuration commands
        "configure_voltage_dc": "CONF:VOLT:DC {range},{resolution},{channels}",
        "configure_voltage_ac": "CONF:VOLT:AC {range},{resolution},{channels}",
        "configure_current_dc": "CONF:CURR:DC {range},{resolution},{channels}",
        "configure_current_ac": "CONF:CURR:AC {range},{resolution},{channels}",
        "configure_resistance_2w": "CONF:RES {range},{resolution},{channels}",
        "configure_resistance_4w": "CONF:FRES {range},{resolution},{channels}",
        "configure_frequency": "CONF:FREQ {range},{resolution},{channels}",
        "configure_period": "CONF:PER {range},{resolution},{channels}",
        "configure_temperature": "CONF:TEMP {sensor_type},{channels}",
        # Scan list management
        "set_scan_list": "ROUT:SCAN {channels}",
        "get_scan_list": "ROUT:SCAN?",
        "clear_scan_list": "ROUT:SCAN (@)",
        # Channel delay
        "set_channel_delay": "ROUT:CHAN:DEL {delay},{channels}",
        "get_channel_delay": "ROUT:CHAN:DEL? {channels}",
        # Trigger control
        "set_trigger_source": "TRIG:SOUR {source}",
        "get_trigger_source": "TRIG:SOUR?",
        "set_trigger_count": "TRIG:COUN {count}",
        "get_trigger_count": "TRIG:COUN?",
        "set_trigger_delay": "TRIG:DEL {delay}",
        "get_trigger_delay": "TRIG:DEL?",
        "set_trigger_timer": "TRIG:TIM {interval}",
        "get_trigger_timer": "TRIG:TIM?",
        # Acquisition control
        "initiate": "INIT",
        "abort": "ABOR",
        "trigger": "*TRG",
        # Data retrieval
        "read": "READ?",
        "fetch": "FETC?",
        "read_remove": "R? {max_readings}",
        "get_data_points": "DATA:POIN?",
        "clear_data": "DATA:DEL NVMEM",
        # Measurement commands (immediate)
        "measure_voltage_dc": "MEAS:VOLT:DC? {range},{resolution},{channels}",
        "measure_voltage_ac": "MEAS:VOLT:AC? {range},{resolution},{channels}",
        "measure_current_dc": "MEAS:CURR:DC? {range},{resolution},{channels}",
        "measure_current_ac": "MEAS:CURR:AC? {range},{resolution},{channels}",
        "measure_resistance_2w": "MEAS:RES? {range},{resolution},{channels}",
        "measure_resistance_4w": "MEAS:FRES? {range},{resolution},{channels}",
        "measure_frequency": "MEAS:FREQ? {range},{resolution},{channels}",
        "measure_temperature": "MEAS:TEMP? {sensor_type},{channels}",
        # Status
        "get_scan_state": "ROUT:SCAN:STAT?",
    }

    # Keysight DAQ series command overrides (34970A, DAQ970A, etc.)
    KEYSIGHT_DAQ_OVERRIDES: Dict[str, str] = {
        # Configuration with AUTO range/resolution support
        "configure_voltage_dc": "CONF:VOLT:DC {range},{resolution},{channels}",
        "configure_voltage_ac": "CONF:VOLT:AC {range},{resolution},{channels}",
        "configure_current_dc": "CONF:CURR:DC {range},{resolution},{channels}",
        "configure_current_ac": "CONF:CURR:AC {range},{resolution},{channels}",
        "configure_resistance_2w": "CONF:RES {range},{resolution},{channels}",
        "configure_resistance_4w": "CONF:FRES {range},{resolution},{channels}",
        # Temperature with sensor type
        "configure_temperature_tc": "CONF:TEMP TC,{tc_type},{channels}",
        "configure_temperature_rtd": "CONF:TEMP RTD,{rtd_type},{channels}",
        "configure_temperature_therm": "CONF:TEMP THER,{therm_type},{channels}",
        # Sample count per trigger
        "set_sample_count": "SAMP:COUN {count}",
        "get_sample_count": "SAMP:COUN?",
        # Advanced trigger modes
        "set_trigger_source_immediate": "TRIG:SOUR IMM",
        "set_trigger_source_timer": "TRIG:SOUR TIM",
        "set_trigger_source_bus": "TRIG:SOUR BUS",
        "set_trigger_source_external": "TRIG:SOUR EXT",
        # Data format
        "set_data_format": "FORM:READ:ALAR {state}",  # Include alarm info
        "set_data_timestamp": "FORM:READ:TIME {state}",  # Include timestamp
        "set_data_channel": "FORM:READ:CHAN {state}",  # Include channel number
        "set_data_unit": "FORM:READ:UNIT {state}",  # Include units
        # Alarm/limit configuration
        "set_alarm_high": "CALC:LIM:UPP {limit},{channels}",
        "get_alarm_high": "CALC:LIM:UPP? {channels}",
        "set_alarm_low": "CALC:LIM:LOW {limit},{channels}",
        "get_alarm_low": "CALC:LIM:LOW? {channels}",
        "set_alarm_enable": "CALC:LIM:STAT {state},{channels}",
        "get_alarm_enable": "CALC:LIM:STAT? {channels}",
        # Scaling (mx+b)
        "set_scaling_gain": "CALC:SCAL:GAIN {gain},{channels}",
        "get_scaling_gain": "CALC:SCAL:GAIN? {channels}",
        "set_scaling_offset": "CALC:SCAL:OFFS {offset},{channels}",
        "get_scaling_offset": "CALC:SCAL:OFFS? {channels}",
        "set_scaling_enable": "CALC:SCAL:STAT {state},{channels}",
        "get_scaling_enable": "CALC:SCAL:STAT? {channels}",
        # DMM digitize mode (fast acquisition)
        "configure_digitize": "ACQ:VOLT:DC {range},{channels}",
        "set_digitize_rate": "ACQ:SRAT {rate}",
        "get_digitize_rate": "ACQ:SRAT?",
        # Monitor a single channel continuously
        "set_monitor_channel": "ROUT:MON {channel}",
        "get_monitor_channel": "ROUT:MON?",
        "set_monitor_enable": "ROUT:MON:STAT {state}",
        "get_monitor_enable": "ROUT:MON:STAT?",
        "read_monitor": "ROUT:MON:DATA?",
        # Module identification
        "get_module_info": "SYST:CTYP? {slot}",
    }

    def __init__(self, variant: str = "generic"):
        """Initialize SCPI command set with variant.

        Args:
            variant: Command variant to use ("generic", "keysight_daq")
        """
        self.variant = variant
        logger.info(f"Initialized DAQ SCPI command set with variant: {variant}")

    def get_command(self, command_name: str, **kwargs) -> str:
        """Get SCPI command string with parameter substitution.

        Uses model-specific commands if available, falls back to generic.

        Args:
            command_name: Name of the command (e.g., "configure_voltage_dc")
            **kwargs: Parameters for command template substitution

        Returns:
            Formatted SCPI command string

        Raises:
            KeyError: If command_name is not found
            ValueError: If required parameters are missing

        Example:
            >>> cmd_set = DAQSCPICommandSet("keysight_daq")
            >>> cmd = cmd_set.get_command("configure_voltage_dc",
            ...                           range="AUTO", resolution="AUTO",
            ...                           channels="(@101:103)")
            >>> print(cmd)
            'CONF:VOLT:DC AUTO,AUTO,(@101:103)'
        """
        # Try model-specific commands first
        if self.variant == "keysight_daq":
            if command_name in self.KEYSIGHT_DAQ_OVERRIDES:
                template = self.KEYSIGHT_DAQ_OVERRIDES[command_name]
                try:
                    return template.format(**kwargs)
                except KeyError as e:
                    raise ValueError(f"Missing required parameter for command '{command_name}': {e}")

        # Fall back to generic SCPI commands
        if command_name in self.GENERIC_COMMANDS:
            template = self.GENERIC_COMMANDS[command_name]
            try:
                return template.format(**kwargs)
            except KeyError as e:
                raise ValueError(f"Missing required parameter for command '{command_name}': {e}")

        raise KeyError(f"Unknown command: '{command_name}' for variant '{self.variant}'")

    def supports_command(self, command_name: str) -> bool:
        """Check if a command is supported by this variant."""
        if self.variant == "keysight_daq" and command_name in self.KEYSIGHT_DAQ_OVERRIDES:
            return True
        return command_name in self.GENERIC_COMMANDS

    def list_commands(self) -> list:
        """Get list of all available command names for this variant."""
        commands = set(self.GENERIC_COMMANDS.keys())
        if self.variant == "keysight_daq":
            commands.update(self.KEYSIGHT_DAQ_OVERRIDES.keys())
        return sorted(commands)
