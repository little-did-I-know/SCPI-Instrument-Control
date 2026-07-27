import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AwgReadout } from "./AwgReadout";
import { useSession } from "../../store/session";

const SESSION = { id: "abc", label: "x", mock: true, address: null, state: "connected", idn: "", model: "SDG1032X", dialect: "", num_channels: 2, viewers: 0, owner: "", kind: "awg" as const };
const CHANNELS = [
  { channel: 1, function: "SINE", frequency: 1000, amplitude: 2, offset: 0, phase: 0, enabled: false, duty_cycle: null, symmetry: null },
  { channel: 2, function: "SQUARE", frequency: 10000, amplitude: 5, offset: 0.5, phase: 90, enabled: true, duty_cycle: null, symmetry: null },
];

beforeEach(() => {
  useSession.getState().clearSession();
  useSession.getState().setSession(SESSION);
});
afterEach(() => vi.restoreAllMocks());

describe("AwgReadout", () => {
  it("renders nothing before the first state arrives", () => {
    const { container } = render(<AwgReadout />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows what every channel reports back", () => {
    useSession.getState().applyAwgState({ channels: CHANNELS });
    render(<AwgReadout />);
    expect(screen.getByText("SINE")).toBeInTheDocument();
    expect(screen.getByText("SQUARE")).toBeInTheDocument();
    expect(screen.getByText(/1000\.000/)).toBeInTheDocument();
    expect(screen.getByText(/5\.000/)).toBeInTheDocument();
  });

  it("shows a disabled channel rather than hiding it", () => {
    // Unlike the scope's strip, which hides disabled channels: for a source,
    // "is this output driving my circuit?" is the question the strip answers,
    // and a hidden channel answers nothing.
    useSession.getState().applyAwgState({ channels: CHANNELS });
    render(<AwgReadout />);
    expect(screen.getByText("Channel 1 off")).toBeInTheDocument();
    expect(screen.getByText("Channel 2 on")).toBeInTheDocument();
  });

  it("shows an unreadable value as --.--, not as 0.000", () => {
    useSession.getState().applyAwgState({ channels: [{ ...CHANNELS[0], frequency: null, amplitude: null, offset: null }] });
    render(<AwgReadout />);
    expect(screen.queryByText("0.000")).not.toBeInTheDocument();
    expect(screen.getAllByText("--.--")).toHaveLength(3);
  });

  it("shows an unknown output state as unknown, not as off", () => {
    useSession.getState().applyAwgState({ channels: [{ ...CHANNELS[0], enabled: null }] });
    render(<AwgReadout />);
    expect(screen.getByText("Channel 1 state unknown")).toBeInTheDocument();
    expect(screen.queryByText("Channel 1 off")).not.toBeInTheDocument();
  });
});
