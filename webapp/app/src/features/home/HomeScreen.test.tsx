import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { HomeScreen } from "./HomeScreen";
import { api } from "../../api/client";
import { getRecent } from "./recent";
import type { DiscoveredDevice, SessionInfo } from "../../api/types";
import { useIdentity } from "../../store/identity";

afterEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
  useIdentity.getState().clearIdentity();
});

const SESSION: SessionInfo = { id: "abc", label: "bench", mock: false, address: "192.168.1.50", state: "connected", idn: "Siglent,SDS824X HD,1,1", model: "SDS824X HD", dialect: "modern", num_channels: 4, viewers: 0, owner: "" };
const FREE: DiscoveredDevice = { address: "192.168.1.51", idn: "x", manufacturer: "Siglent", model: "SDS1104X-E", dialect: "legacy", kind: "scope", connected: false };

describe("HomeScreen", () => {
  it("shows discovered instruments and connects a free one", async () => {
    vi.spyOn(api, "listSessions").mockResolvedValue([]);
    vi.spyOn(api, "discover").mockResolvedValue([FREE]);
    const created = { ...SESSION, id: "new", address: "192.168.1.51", model: "SDS1104X-E" };
    const createSession = vi.spyOn(api, "createSession").mockResolvedValue(created);
    const onConnected = vi.fn();
    render(<HomeScreen onConnected={onConnected} />);

    await screen.findByRole("button", { name: "Connect SDS1104X-E" });
    await userEvent.click(screen.getByRole("button", { name: "Connect SDS1104X-E" }));

    await waitFor(() => expect(createSession).toHaveBeenCalledWith({ address: "192.168.1.51", label: "SDS1104X-E" }));
    await waitFor(() => expect(onConnected).toHaveBeenCalledWith(created));
  });

  it("seeds held sessions into the Your-sessions zone on mount", async () => {
    vi.spyOn(api, "listSessions").mockResolvedValue([SESSION]);
    vi.spyOn(api, "discover").mockResolvedValue([]);
    render(<HomeScreen onConnected={vi.fn()} />);
    await screen.findByRole("button", { name: "Open SDS824X HD" });
  });

  it("paints a real held session before the discover scan resolves", async () => {
    const held: SessionInfo = { ...SESSION, id: "held1", address: "192.168.1.50", model: "SDS824X HD" };
    vi.spyOn(api, "listSessions").mockResolvedValue([held]);
    // discover is slow: resolves only when we let it
    let resolveDiscover: (v: DiscoveredDevice[]) => void = () => {};
    vi.spyOn(api, "discover").mockReturnValue(new Promise<DiscoveredDevice[]>((r) => { resolveDiscover = r; }));
    render(<HomeScreen onConnected={vi.fn()} />);
    // held session's Open button is present BEFORE discover resolves
    expect(await screen.findByRole("button", { name: "Open SDS824X HD" })).toBeInTheDocument();
    resolveDiscover([]);
  });

  it("opens a held session, records it in recent, and calls onConnected", async () => {
    vi.spyOn(api, "listSessions").mockResolvedValue([SESSION]);
    vi.spyOn(api, "discover").mockResolvedValue([]);
    const getSession = vi.spyOn(api, "getSession").mockResolvedValue(SESSION);
    const onConnected = vi.fn();
    render(<HomeScreen onConnected={onConnected} />);

    await userEvent.click(await screen.findByRole("button", { name: "Open SDS824X HD" }));

    await waitFor(() => expect(getSession).toHaveBeenCalledWith("abc"));
    await waitFor(() => expect(onConnected).toHaveBeenCalledWith(SESSION));
    await waitFor(() => expect(getRecent().map((r) => r.model)).toContain("SDS824X HD"));
  });

  it("connects to a manually entered IP", async () => {
    vi.spyOn(api, "listSessions").mockResolvedValue([]);
    vi.spyOn(api, "discover").mockResolvedValue([]);
    const created = { ...SESSION, id: "man", address: "10.0.0.9", model: "10.0.0.9" };
    const createSession = vi.spyOn(api, "createSession").mockResolvedValue(created);
    const onConnected = vi.fn();
    render(<HomeScreen onConnected={onConnected} />);

    await userEvent.type(await screen.findByLabelText("IP address"), "10.0.0.9");
    await userEvent.click(screen.getByRole("button", { name: "Connect" }));

    await waitFor(() => expect(createSession).toHaveBeenCalledWith({ address: "10.0.0.9", label: "10.0.0.9" }));
    await waitFor(() => expect(onConnected).toHaveBeenCalledWith(created));
  });

  it("does not re-scan on the interval while a connect is in flight", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      vi.spyOn(api, "listSessions").mockResolvedValue([]);
      const discover = vi.spyOn(api, "discover").mockResolvedValue([FREE]);
      vi.spyOn(api, "createSession").mockReturnValue(new Promise<SessionInfo>(() => {})); // never resolves — connect stays in flight
      render(<HomeScreen onConnected={vi.fn()} />);

      await vi.waitFor(() => expect(discover).toHaveBeenCalledTimes(1));
      await user.click(await screen.findByRole("button", { name: "Connect SDS1104X-E" }));

      // Two full refresh cycles pass while busy — the interval must not fire another scan.
      await vi.advanceTimersByTimeAsync(30_000);
      await vi.advanceTimersByTimeAsync(30_000);
      expect(discover).toHaveBeenCalledTimes(1);
    } finally {
      vi.useRealTimers();
    }
  });

  it("connects a mock scope from the rail", async () => {
    vi.spyOn(api, "listSessions").mockResolvedValue([]);
    vi.spyOn(api, "discover").mockResolvedValue([]);
    const createSession = vi.spyOn(api, "createSession").mockResolvedValue({ ...SESSION, mock: true, address: null });
    const onConnected = vi.fn();
    render(<HomeScreen onConnected={onConnected} />);
    await userEvent.click(await screen.findByRole("button", { name: /mock scope/i }));
    await waitFor(() => expect(createSession).toHaveBeenCalledWith({ mock: true }));
    await waitFor(() => expect(onConnected).toHaveBeenCalled());
  });

  it("surfaces a connect error detail", async () => {
    const { ApiError } = await import("../../api/client");
    vi.spyOn(api, "listSessions").mockResolvedValue([]);
    vi.spyOn(api, "discover").mockResolvedValue([FREE]);
    vi.spyOn(api, "createSession").mockRejectedValue(new ApiError(504, "SiglentTimeoutError", "connection timed out"));
    render(<HomeScreen onConnected={vi.fn()} />);
    await userEvent.click(await screen.findByRole("button", { name: "Connect SDS1104X-E" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("connection timed out");
  });
});

describe("HomeScreen ownership badge", () => {
  const OWNED: SessionInfo = { ...SESSION, id: "owned1", address: "192.168.1.52", owner: "alice" };

  it("shows the read-only badge and claim control for a session owned by someone else", async () => {
    useIdentity.getState().setIdentity("robin");
    vi.spyOn(api, "listSessions").mockResolvedValue([OWNED]);
    vi.spyOn(api, "discover").mockResolvedValue([]);
    render(<HomeScreen onConnected={vi.fn()} />);

    await screen.findByRole("button", { name: "Open SDS824X HD" });
    expect(screen.getByText(/read-only/i)).toBeInTheDocument();
    expect(screen.getByText(/alice/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /claim/i })).toBeInTheDocument();
  });

  it("hides the badge when the viewer is the session's own owner", async () => {
    useIdentity.getState().setIdentity("alice");
    vi.spyOn(api, "listSessions").mockResolvedValue([OWNED]);
    vi.spyOn(api, "discover").mockResolvedValue([]);
    render(<HomeScreen onConnected={vi.fn()} />);

    await screen.findByRole("button", { name: "Open SDS824X HD" });
    expect(screen.queryByText(/read-only/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /claim/i })).not.toBeInTheDocument();
  });

  it("hides the badge for an unowned session (writable by anyone)", async () => {
    useIdentity.getState().setIdentity("robin");
    vi.spyOn(api, "listSessions").mockResolvedValue([SESSION]); // owner: ""
    vi.spyOn(api, "discover").mockResolvedValue([]);
    render(<HomeScreen onConnected={vi.fn()} />);

    await screen.findByRole("button", { name: "Open SDS824X HD" });
    expect(screen.queryByText(/read-only/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /claim/i })).not.toBeInTheDocument();
  });

  it("does not disable the Open button for a non-owner (reads stay available)", async () => {
    useIdentity.getState().setIdentity("robin");
    vi.spyOn(api, "listSessions").mockResolvedValue([OWNED]);
    vi.spyOn(api, "discover").mockResolvedValue([]);
    render(<HomeScreen onConnected={vi.fn()} />);

    const open = await screen.findByRole("button", { name: "Open SDS824X HD" });
    expect(open).toBeEnabled();
  });

  it("surfaces a failed claim's detail without getting stuck", async () => {
    useIdentity.getState().setIdentity("robin");
    vi.spyOn(api, "listSessions").mockResolvedValue([OWNED]);
    vi.spyOn(api, "discover").mockResolvedValue([]);
    const { ApiError } = await import("../../api/client");
    vi.spyOn(api, "claimSession").mockRejectedValue(new ApiError(409, "Conflict", "owner is actively watching the stream"));
    render(<HomeScreen onConnected={vi.fn()} />);

    await screen.findByRole("button", { name: "Open SDS824X HD" });
    const claim = screen.getByRole("button", { name: /claim/i });
    await userEvent.click(claim);

    expect(await screen.findByRole("alert")).toHaveTextContent("owner is actively watching the stream");
    expect(claim).toBeEnabled();
    expect(screen.getByText(/read-only/i)).toBeInTheDocument();
  });

  it("refreshes the session list after a successful claim, so the badge reflects the new owner", async () => {
    useIdentity.getState().setIdentity("robin");
    // The claim doesn't push its response into state on its own — HomeScreen
    // must re-fetch, so simulate the server reporting the new owner on the
    // *next* listSessions call, same as it would after a real claim.
    const listSessions = vi.spyOn(api, "listSessions").mockResolvedValueOnce([OWNED]).mockResolvedValue([{ ...OWNED, owner: "robin" }]);
    vi.spyOn(api, "discover").mockResolvedValue([]);
    vi.spyOn(api, "claimSession").mockResolvedValue({ ...OWNED, owner: "robin" });
    render(<HomeScreen onConnected={vi.fn()} />);

    await screen.findByRole("button", { name: "Open SDS824X HD" });
    const callsBefore = listSessions.mock.calls.length;
    await userEvent.click(screen.getByRole("button", { name: /claim/i }));

    await waitFor(() => expect(listSessions.mock.calls.length).toBeGreaterThan(callsBefore));
    await waitFor(() => expect(screen.queryByText(/read-only/i)).not.toBeInTheDocument());
  });
});
