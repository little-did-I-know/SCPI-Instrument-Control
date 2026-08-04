"""Verify scope.capabilities claims against a real modern-dialect scope.

Usage: PYTHONPATH=. python scripts/verify_capabilities_hardware.py 192.168.1.207

Run it with PYTHONPATH=. from the repository root. Python puts the SCRIPT's own
directory on sys.path, not the repo root, so a bare invocation resolves
`scpi_control` through whatever editable install is active -- which on a
worktree checkout is a DIFFERENT tree than the one under test, quietly turning
the output into evidence about the wrong code.

For every public token in the connected scope's capability sets, this sets the
token, drains SYST:ERR?, reads the value back, and restores the original
setting. Results are classified three ways:

  PASS     the token round-trips with no error queued.
  COERCED  accepted with no error queued, but the scope answers with a
           different token -- it silently did something else. A fact about the
           attached MODEL (e.g. no external trigger input), not a driver
           defect, so it is reported but does not fail the run.
  FAIL     an error was queued or the driver raised -- the capability tables
           over-claim, and the table is what must change.

Also records the exact echo casing of the :TRIGger:TYPE / :TRIGger:MODE /
:TRIGger:EDGE:SLOPe / :TRIGger:EDGE:COUPling responses, writing each token in
three casings so the output distinguishes "echoes what you sent" from "echoes
its own canonical spelling" -- that answers what a faithful mock must store.

Every channel is switched ON before the trigger-source check: a channel that is
off cannot be the trigger source and is silently coerced to LINE, so leaving
them alone measures the channel switches instead of the source vocabulary.
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
    """Set each token, drain SYST:ERR?, read it back, and classify the result.

    Three outcomes, deliberately distinguished:

    PASS     the token round-trips with no error queued.
    COERCED  no error queued, but the instrument answers with a DIFFERENT
             token than the one written -- it accepted the command and
             silently did something else. This is a real hardware-capability
             finding, not a driver defect, so it does not fail the run; the
             capability sets report what the driver can send for the dialect
             and cannot know what a given model physically has.
    FAIL     the instrument queued an error, or the driver raised.
    """
    results = []
    for token in sorted(tokens):
        try:
            set_fn(token)
            errors = drain_errors(scope)
            readback = get_fn()
            if errors:
                status = f"FAIL errors={errors} readback={readback!r}"
            elif readback != token:
                status = f"COERCED -> {readback!r} (accepted, no error queued)"
            else:
                status = "PASS"
            results.append((label, token, status))
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

        # Raw echo casing for the mock-fidelity record (wave-1 queued item).
        # Writes the same token in three casings: this separates "the scope
        # echoes what you sent" from "the scope echoes its own canonical
        # spelling", which decides what a faithful mock must store.
        print("\n--- echo casing (write casing -> query response) ---")
        for setter, query, sent in (
            (":TRIGger:TYPE", ":TRIGger:TYPE?", ("SLOPe", "SLOPE", "slope")),
            (":TRIGger:MODE", ":TRIGger:MODE?", ("NORMal", "NORMAL", "normal")),
            (":TRIGger:EDGE:SLOPe", ":TRIGger:EDGE:SLOPe?", ("RISing", "RISING", "rising")),
            (":TRIGger:EDGE:COUPling", ":TRIGger:EDGE:COUPling?", ("HFREJect", "HFREJECT", "hfreject")),
        ):
            before = scope.query(query)
            for casing in sent:
                scope.write(f"{setter} {casing}")
                print(f"ECHO {setter:<24} sent {casing!r:<12} -> {scope.query(query)!r}")
            scope.write(f"{setter} {before}")
        scope.write(":TRIGger:TYPE EDGE")

        # Edge-source acceptance (EX/EX5/LINE are driver pass-throughs today).
        # A channel that is switched OFF cannot be the trigger source -- the
        # scope silently coerces to LINE -- so enable every channel first, or
        # this measures the channel switches rather than the source vocabulary.
        original_source = scope.trigger.source
        original_switch = {}
        for number in range(1, scope.model_capability.num_channels + 1):
            channel = scope.get_channel(number)
            if channel is not None:
                original_switch[number] = channel.enabled
                channel.enable()

        def restore_sources():
            setattr(scope.trigger, "source", original_source)
            for num, was_on in original_switch.items():
                scope.get_channel(num).enabled = was_on

        results += check_tokens(
            scope,
            "trigger_source",
            caps.trigger_sources,
            lambda t: setattr(scope.trigger, "source", t),
            lambda: scope.trigger.source,
            restore_sources,
        )

        failures = [r for r in results if r[2].startswith("FAIL")]
        coerced = [r for r in results if r[2].startswith("COERCED")]
        passed = [r for r in results if r[2] == "PASS"]
        print("\n--- capability claims ---")
        for row in results:
            print("{:>18}  {:<10}  {}".format(*row))

        model = scope.device_info["model"]
        print(f"\n{len(passed)}/{len(results)} capability claims round-tripped on {model}")
        if coerced:
            print(f"{len(coerced)} silently coerced (accepted, no error queued) -- a fact about this")
            print("model, not a driver defect. Document it; do not restrict the dialect-wide set:")
            for label, token, status in coerced:
                print(f"    {label} {token}: {status}")
        if failures:
            print(f"{len(failures)} FAILED -- the capability tables over-claim; fix the table:")
            for label, token, status in failures:
                print(f"    {label} {token}: {status}")
        sys.exit(1 if failures else 0)
    finally:
        scope.disconnect()


if __name__ == "__main__":
    main()
