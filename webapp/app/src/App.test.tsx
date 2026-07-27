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

  it("does NOT render the scope rail for a psu session, and renders the PSU panel instead", async () => {
    useSession.getState().setSession({ ...SESSION, kind: "psu" });
    render(<App />);
    expect(screen.queryByText("Channels")).not.toBeInTheDocument();
    expect(screen.queryByText(/coming soon/i)).not.toBeInTheDocument();
    expect(await screen.findByLabelText("Output 1 voltage")).toBeInTheDocument();
    expect(screen.getByLabelText("Output 1 enable")).not.toBeChecked();
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
    useSession.getState().setSession({ ...SESSION, kind: "awg" });
    render(<App />);
    expect(screen.getByText(/coming soon/i)).toBeInTheDocument();
    expect(screen.queryByText("Channels")).not.toBeInTheDocument();
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
});
