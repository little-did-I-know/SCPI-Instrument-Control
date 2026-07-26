import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import { setToken } from "./api/token";
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

  it("does NOT render the scope rail for a psu session", () => {
    useSession.getState().setSession({ ...SESSION, kind: "psu" });
    render(<App />);
    expect(screen.queryByText("Channels")).not.toBeInTheDocument();
  });

  it("renders the home screen with no session", () => {
    render(<App />);
    expect(screen.queryByText("Channels")).not.toBeInTheDocument();
  });
});
