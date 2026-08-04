"""Verify scope.capabilities claims against a real modern-dialect scope.

Usage: python scripts/verify_capabilities_hardware.py 192.168.1.207

For every public token in the connected scope's capability sets, this sets the
token, drains SYST:ERR?, reads the value back, and restores the original
setting. A claim PASSES when no error is queued and the read-back round-trips.
Also records (a) the exact echo casing of :TRIGger:TYPE? / :TRIGger:MODE? /
:TRIGger:EDGE:SLOPe? responses (queued wave-1 item: mock echo casing is
unmeasured) and (b) whether EX / EX5 / LINE are accepted as edge sources
(supported_trigger_sources reports driver behavior, not a hardware promise --
this measures the hardware half).
"""

import sys

from scpi_control import Oscilloscope
from scpi_control import exceptions


def drain_errors(scope):
    errors = []
    for _ in range(10):
        response = scope.query("SYST:ERR?").strip()
        if response.startswith(("+0", "0,")):
            break
        errors.append(response)
    return errors


def check_tokens(scope, label, tokens, set_fn, get_fn, restore):
    results = []
    for token in sorted(tokens):
        try:
            set_fn(token)
            errors = drain_errors(scope)
            readback = get_fn()
            ok = not errors and readback == token
            results.append((label, token, "PASS" if ok else f"FAIL errors={errors} readback={readback!r}"))
        except exceptions.SiglentError as exc:
            results.append((label, token, f"FAIL raised {type(exc).__name__}: {exc}"))
    restore()
    return results


def main():
    host = sys.argv[1] if len(sys.argv) > 1 else "192.168.1.207"
    scope = Oscilloscope(host)
    scope.connect()
    try:
        assert scope.dialect == "modern", f"expected the modern dialect, got {scope.dialect}"
        caps = scope.capabilities
        results = []

        original_coupling = scope.channel1.coupling
        results += check_tokens(
            scope,
            "channel_coupling",
            caps.channel_couplings,
            lambda t: setattr(scope.channel1, "coupling", t),
            lambda: scope.channel1.coupling,
            lambda: setattr(scope.channel1, "coupling", original_coupling),
        )

        original_slope = scope.trigger.slope
        results += check_tokens(
            scope,
            "trigger_slope",
            caps.trigger_slopes,
            lambda t: setattr(scope.trigger, "slope", t),
            lambda: scope.trigger.slope,
            lambda: setattr(scope.trigger, "slope", original_slope),
        )

        original_tcoupling = scope.trigger.coupling
        results += check_tokens(
            scope,
            "trigger_coupling",
            caps.trigger_couplings,
            lambda t: setattr(scope.trigger, "coupling", t),
            lambda: scope.trigger.coupling,
            lambda: setattr(scope.trigger, "coupling", original_tcoupling),
        )

        original_type = scope.trigger.trigger_type
        results += check_tokens(
            scope,
            "trigger_type",
            caps.trigger_types,
            lambda t: setattr(scope.trigger, "trigger_type", t),
            lambda: scope.trigger.trigger_type,
            lambda: setattr(scope.trigger, "trigger_type", original_type),
        )

        original_mode = scope.trigger.mode
        results += check_tokens(
            scope,
            "trigger_mode",
            caps.trigger_modes,
            lambda t: setattr(scope.trigger, "mode", t),
            lambda: scope.trigger.mode,
            lambda: setattr(scope.trigger, "mode", original_mode),
        )

        # Raw echo casing for the mock-fidelity record (wave-1 queued item):
        for query in (":TRIGger:TYPE?", ":TRIGger:MODE?", ":TRIGger:EDGE:SLOPe?"):
            print(f"ECHO {query} -> {scope.query(query)!r}")

        # Edge-source acceptance (EX/EX5/LINE are driver pass-throughs today):
        original_source = scope.trigger.source
        results += check_tokens(
            scope,
            "trigger_source",
            caps.trigger_sources,
            lambda t: setattr(scope.trigger, "source", t),
            lambda: scope.trigger.source,
            lambda: setattr(scope.trigger, "source", original_source),
        )

        failures = [r for r in results if not r[2].startswith("PASS")]
        for row in results:
            print("{:>18}  {:<10}  {}".format(*row))
        print(f"\n{len(results) - len(failures)}/{len(results)} capability claims verified on {scope.device_info['model']}")
        sys.exit(1 if failures else 0)
    finally:
        scope.disconnect()


if __name__ == "__main__":
    main()
