import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { InstrumentShell } from "./InstrumentShell";
import { useTerminalDrawer } from "./useTerminalDrawer";
import { api } from "../../api/client";
import { setToken } from "../../api/token";
import { useSession } from "../../store/session";

const SCOPE_SESSION = { id: "scope-1", label: "x", mock: true, address: null, state: "connected", idn: "", model: "", dialect: "legacy", num_channels: 4, viewers: 0, owner: "", kind: "scope" as const };
const PSU_SESSION = { id: "psu-1", label: "y", mock: true, address: null, state: "connected", idn: "", model: "SPD3303X", dialect: "", num_channels: 2, viewers: 0, owner: "", kind: "psu" as const };

beforeEach(() => {
  localStorage.clear();
  setToken("test-token");
  useSession.getState().clearSession();
  useTerminalDrawer.getState().close();
});
afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

// InstrumentShell.tsx:17-19 closes the drawer whenever the session id
// changes. The scenario this guards: open the terminal against a scope,
// disconnect, connect a power supply -- without the reset, the drawer would
// reopen against an instrument with a different command set and a stale
// command log left over from the previous session.
describe("InstrumentShell", () => {
  it("closes the terminal drawer when the session changes", () => {
    vi.spyOn(api, "psuState").mockResolvedValue({ outputs: [] });
    useSession.getState().setSession(SCOPE_SESSION);
    const { rerender } = render(<InstrumentShell />);

    useTerminalDrawer.getState().toggle();
    rerender(<InstrumentShell />);
    expect(screen.getByRole("region", { name: "SCPI terminal" })).toBeInTheDocument();

    useSession.getState().setSession(PSU_SESSION);
    rerender(<InstrumentShell />);
    expect(screen.queryByRole("region", { name: "SCPI terminal" })).not.toBeInTheDocument();
  });

  it("leaves the drawer alone on a re-render that keeps the same session", () => {
    useSession.getState().setSession(SCOPE_SESSION);
    const { rerender } = render(<InstrumentShell />);

    useTerminalDrawer.getState().toggle();
    rerender(<InstrumentShell />);
    expect(screen.getByRole("region", { name: "SCPI terminal" })).toBeInTheDocument();

    rerender(<InstrumentShell />);
    expect(screen.getByRole("region", { name: "SCPI terminal" })).toBeInTheDocument();
  });
});
