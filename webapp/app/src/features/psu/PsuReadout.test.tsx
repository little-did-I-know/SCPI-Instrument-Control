import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { PsuReadout } from "./PsuReadout";
import { useSession } from "../../store/session";

const SESSION = { id: "abc", label: "x", mock: true, address: null, state: "connected", idn: "", model: "SPD3303X", dialect: "", num_channels: 2, viewers: 0, owner: "", kind: "psu" as const };
const OUTPUTS = [
  { output: 1, voltage: 3.3, current: 0.5, enabled: false, measured_voltage: 0.0, measured_current: 0.0, measured_power: 0.0 },
  { output: 2, voltage: 5.0, current: 1.0, enabled: true, measured_voltage: 5.01, measured_current: 0.12, measured_power: 0.6 },
];

beforeEach(() => {
  useSession.getState().clearSession();
  useSession.getState().setSession(SESSION);
});
afterEach(() => vi.restoreAllMocks());

describe("PsuReadout", () => {
  it("renders nothing before the first state arrives", () => {
    const { container } = render(<PsuReadout />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows the measured values for every output", () => {
    useSession.getState().applyPsuState({ outputs: OUTPUTS });
    render(<PsuReadout />);
    expect(screen.getByText(/5\.010/)).toBeInTheDocument();
    expect(screen.getByText(/0\.120/)).toBeInTheDocument();
    expect(screen.getByText(/0\.600/)).toBeInTheDocument();
  });

  it("shows which outputs are live, accessibly and not only by colour", () => {
    useSession.getState().applyPsuState({ outputs: OUTPUTS });
    render(<PsuReadout />);
    expect(screen.getByText("Output 1 off")).toBeInTheDocument();
    expect(screen.getByText("Output 2 on")).toBeInTheDocument();
  });

  it("shows a failed measurement as --.--, not as 0.000", () => {
    // A reading the supply would not give us is null, and null is not zero.
    // Painting it 0.000 is a confident lie about live hardware.
    useSession.getState().applyPsuState({ outputs: [{ ...OUTPUTS[0], measured_voltage: null, measured_current: null, measured_power: null }] });
    render(<PsuReadout />);
    expect(screen.queryByText("0.000")).not.toBeInTheDocument();
    expect(screen.getAllByText("--.--")).toHaveLength(3);
  });

  it("shows an unknown output state as unknown, not as off", () => {
    // An SPD3303X's CH3 answers no output-state query at all. An energised rail
    // shown as a confident "off" is the dangerous direction.
    useSession.getState().applyPsuState({ outputs: [{ ...OUTPUTS[0], enabled: null }] });
    render(<PsuReadout />);
    expect(screen.getByText("Output 1 state unknown")).toBeInTheDocument();
    expect(screen.queryByText("Output 1 off")).not.toBeInTheDocument();
  });
});
