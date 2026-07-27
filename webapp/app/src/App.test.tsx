import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import { setToken } from "./api/token";
import { useTerminalDrawer } from "./features/shell/useTerminalDrawer";
import { useSession } from "./store/session";

// TokenGate's own suite (features/auth/TokenGate.test.tsx) already covers its
// async "checking" -> "ready" flow. Going through the real gate here would
// force every assertion below behind a waitFor for the whoami round-trip,
// which is not what this suite is testing. Per the brief: mock the gate
// rather than weaken the (synchronous) render assertions it specifies.
vi.mock("./features/auth/TokenGate", () => ({
  TokenGate: ({ children }: { children: React.ReactNode }) => children,
}));

const SESSION = { id: "abc", label: "x", mock: true, address: null, state: "connected", idn: "", model: "", dialect: "legacy", num_channels: 4, viewers: 0, owner: "", kind: "scope" as const };

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

class FakeWebSocket {
  onmessage: ((event: { data: string }) => void) | null = null;
  onclose: ((event: { code: number }) => void) | null = null;
  onerror: (() => void) | null = null;
  close() {}
}

beforeEach(() => {
  localStorage.clear();
  setToken("test-token"); // past TokenGate; matches the other suites
  useSession.getState().clearSession();
  useTerminalDrawer.getState().close();
  vi.stubGlobal("WebSocket", FakeWebSocket as unknown as typeof WebSocket);
  // HomeScreen (no-session case) and useReferenceSeed (scope/psu cases) both
  // hit the network on mount even with the gate mocked out, so fetch needs an
  // answer for every path a real App render can take.
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.includes("/api/whoami")) return Promise.resolve(jsonResponse({ identity: "test" }));
      if (url.endsWith("/api/sessions")) return Promise.resolve(jsonResponse([]));
      if (url.includes("/api/discover")) return Promise.resolve(jsonResponse([]));
      if (url.includes("/reference")) return Promise.resolve(jsonResponse({ name: null, channel: null, t0: 0, dt: 0, points: [] }));
      if (url.includes("/psu/state")) {
        return Promise.resolve(
          jsonResponse({
            outputs: [{ output: 1, voltage: 3.3, current: 0.5, enabled: false, measured_voltage: 0.0, measured_current: 0.0, measured_power: 0.0 }],
          }),
        );
      }
      if (url.includes("/awg/state")) {
        return Promise.resolve(
          jsonResponse({
            channels: [{ channel: 1, function: "SINE", frequency: null, amplitude: null, offset: null, phase: null, enabled: null, duty_cycle: null, symmetry: null }],
          }),
        );
      }
      return Promise.resolve(jsonResponse({}));
    }),
  );
});
afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("App view selection", () => {
  it("renders the scope rail for a scope session", () => {
    useSession.getState().setSession(SESSION);
    render(<App />);
    expect(screen.getByText("Channels")).toBeInTheDocument();
  });

  // Closes the registry hole from the branch review: kindViews.test.tsx only
  // ever asserted `typeof view.body === "function"`, so `readout` could be
  // deleted from a KIND_VIEWS entry -- silently dropping the scope's PKPK/FREQ
  // strip or the PSU's measured V/I/P -- and the whole suite would stay green.
  // This renders <App /> end to end (not ReadoutStrip/PsuReadout in isolation)
  // so the assertion actually exercises InstrumentShell's registry lookup.
  it("renders the scope readout strip through the registry, not just the rail", () => {
    useSession.getState().setSession(SESSION);
    // setSession resets scope/psu to null, so the state must be applied after.
    useSession.getState().applyState({
      run_state: "TRIGD",
      timebase: 0.001,
      channels: { "1": { enabled: true, voltage_scale: 0.5, voltage_offset: 0, coupling: "DC", probe_ratio: 10 } },
      trigger: { mode: "AUTO", source: "C1", level: 0, slope: "POS", coupling: "DC" },
    });
    useSession.getState().applyMeasurements([{ channel: 1, mtype: "PKPK", value: 2.5 }]);
    render(<App />);
    // "C1" alone is ambiguous (ChannelsPanel's own GroupBox title is also
    // "C1"); the coupling/scale line only ReadoutStrip renders disambiguates it.
    expect(screen.getByText("DC · 0.5 V/div")).toBeInTheDocument();
    expect(screen.getByText(/2\.500/)).toBeInTheDocument();
  });

  it("does NOT render the scope rail for a psu session, and renders the PSU panel instead", async () => {
    useSession.getState().setSession({ ...SESSION, kind: "psu" });
    render(<App />);
    expect(screen.queryByText("Channels")).not.toBeInTheDocument();
    expect(screen.queryByText(/coming soon/i)).not.toBeInTheDocument();
    expect(await screen.findByLabelText("Output 1 voltage")).toBeInTheDocument();
    expect(screen.getByLabelText("Output 1 enable")).not.toBeChecked();
  });

  // Same registry hole as above, but for the PSU side, and combined with the
  // two safety properties the branch review flagged as only checked against
  // <PsuReadout /> in isolation: a measurement the instrument could not give
  // us must render as "--.--", never "0.000", and an unreadable enable state
  // must read as unknown, never as a confident "off".
  it("renders unreadable psu measurements as --.-- (never 0.000) and an unknown enable state, through the registry", async () => {
    useSession.getState().setSession({ ...SESSION, kind: "psu" });
    (fetch as unknown as ReturnType<typeof vi.fn>).mockImplementation((input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.includes("/api/whoami")) return Promise.resolve(jsonResponse({ identity: "test" }));
      if (url.endsWith("/api/sessions")) return Promise.resolve(jsonResponse([]));
      if (url.includes("/api/discover")) return Promise.resolve(jsonResponse([]));
      if (url.includes("/psu/state")) {
        return Promise.resolve(
          jsonResponse({
            outputs: [
              { output: 1, voltage: 3.3, current: 0.5, enabled: null, measured_voltage: null, measured_current: null, measured_power: null },
            ],
          }),
        );
      }
      return Promise.resolve(jsonResponse({}));
    });
    render(<App />);
    expect(await screen.findByText("Output 1 state unknown")).toBeInTheDocument();
    expect(screen.queryByText("Output 1 off")).not.toBeInTheDocument();
    expect(screen.getAllByText("--.--")).toHaveLength(3);
    expect(screen.queryByText("0.000")).not.toBeInTheDocument();
  });

  it("does not seed the scope reference overlay for a psu session", async () => {
    // /scope/reference is behind require_kind now, so seeding it on a PSU
    // mount is a guaranteed 400 on every single mount.
    useSession.getState().setSession({ ...SESSION, kind: "psu" });
    render(<App />);
    await screen.findByLabelText("Output 1 voltage");
    const urls = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls.map((c: unknown[]) => String(c[0]));
    expect(urls.some((u: string) => u.includes("/scope/"))).toBe(false);
  });

  it("renders the home screen with no session", () => {
    render(<App />);
    expect(screen.queryByText("Channels")).not.toBeInTheDocument();
  });

  it("renders the coming-soon fallback for a kind with no registered view", () => {
    // awg now has a registered view (AwgPanel/AwgReadout); daq is still the
    // kind with no entry in KIND_VIEWS, so it is the one that must fall back.
    useSession.getState().setSession({ ...SESSION, kind: "daq" });
    render(<App />);
    expect(screen.getByText(/coming soon/i)).toBeInTheDocument();
    expect(screen.queryByText("Channels")).not.toBeInTheDocument();
  });

  it("mounts the AWG readout through the registry, with unreadable values shown as unknown", async () => {
    // Guards the registry's `readout` half: without it, deleting `readout:`
    // from the awg entry removes the strip with every test still green.
    useSession.getState().setSession({ ...SESSION, kind: "awg" });
    render(<App />);
    expect(await screen.findByLabelText("Channel 1 frequency")).toBeInTheDocument();
    expect(screen.getByText("Channel 1 state unknown")).toBeInTheDocument();
    expect(screen.queryByText("0.000")).not.toBeInTheDocument();
  });

  it("offers the SCPI terminal for a psu session, not just a scope", async () => {
    // The reason this sub-project exists: the console is kind-agnostic code
    // that only a scope could reach.
    useSession.getState().setSession({ ...SESSION, kind: "psu" });
    render(<App />);
    await userEvent.click(screen.getByRole("button", { name: /terminal/i }));
    expect(screen.getByRole("region", { name: "SCPI terminal" })).toBeInTheDocument();
  });

  it("offers the SCPI terminal for a scope session", async () => {
    useSession.getState().setSession(SESSION);
    render(<App />);
    await userEvent.click(screen.getByRole("button", { name: /terminal/i }));
    expect(screen.getByRole("region", { name: "SCPI terminal" })).toBeInTheDocument();
  });

  it("does not offer the terminal with no session", () => {
    render(<App />);
    expect(screen.queryByRole("button", { name: /terminal/i })).not.toBeInTheDocument();
  });

  it("surfaces a session error in the app, not just in the store", () => {
    // Guards the wiring: the banner exists but is useless if the shell never
    // renders it.
    useSession.getState().setSession(SESSION);
    useSession.getState().setError("connection lost");
    render(<App />);
    expect(screen.getByRole("alert")).toHaveTextContent("connection lost");
  });

  it("reports its expanded state and target on the terminal toggle button", async () => {
    useSession.getState().setSession(SESSION);
    render(<App />);
    const button = screen.getByRole("button", { name: /terminal/i });
    expect(button).toHaveAttribute("aria-expanded", "false");
    // aria-controls must name the actual drawer element, not just any id.
    const controlsId = button.getAttribute("aria-controls");
    expect(controlsId).toBeTruthy();
    await userEvent.click(button);
    expect(button).toHaveAttribute("aria-expanded", "true");
    const drawer = screen.getByRole("region", { name: "SCPI terminal" });
    expect(drawer).toHaveAttribute("id", controlsId);
  });
});
