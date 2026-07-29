import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Sessions } from "./Sessions";
import { adminApi, type Session as SessionRow } from "./api";

const session = (overrides: Partial<SessionRow> = {}): SessionRow => ({
  id: "s1",
  label: "bench-1",
  kind: "scope",
  mock: true,
  address: null,
  state: "connected",
  idn: "Mock,Scope,1,1.0",
  model: "Mock Scope",
  dialect: "generic",
  num_channels: 4,
  viewers: 0,
  owner: "",
  idle_seconds: 12.3,
  ...overrides,
});

describe("Sessions", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("lists sessions with instrument, owner, viewers and idle time", async () => {
    vi.spyOn(adminApi, "sessions").mockResolvedValue([
      session({ id: "s1", mock: true, owner: "bob", viewers: 2, idle_seconds: 5.5 }),
    ]);
    render(<Sessions />);
    expect(await screen.findByText(/mock/i)).toBeInTheDocument();
    expect(screen.getByText(/bob/)).toBeInTheDocument();
    expect(screen.getByText(/2/)).toBeInTheDocument();
    expect(screen.getByText(/5\.5/)).toBeInTheDocument();
  });

  it("renders an address instead of Mock for a real instrument", async () => {
    vi.spyOn(adminApi, "sessions").mockResolvedValue([
      session({ id: "s1", mock: false, address: "192.168.1.20:5025" }),
    ]);
    render(<Sessions />);
    expect(await screen.findByText(/192\.168\.1\.20:5025/)).toBeInTheDocument();
  });

  it("shows a dash for an unowned session", async () => {
    vi.spyOn(adminApi, "sessions").mockResolvedValue([session({ id: "s1", owner: "" })]);
    render(<Sessions />);
    await screen.findByText(/bench-1/);
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("renders an error state when the listing fails", async () => {
    vi.spyOn(adminApi, "sessions").mockRejectedValue(new Error("gateway unreachable"));
    render(<Sessions />);
    expect(await screen.findByRole("alert")).toHaveTextContent(/gateway unreachable/i);
  });

  it("releases a session without confirmation and reloads the listing", async () => {
    // sessions() returns bob's session on mount, then an unowned one on the
    // reload that must follow a successful release. A local optimistic patch
    // (clearing owner in state without calling the server again) would leave
    // the call count flat, so that assertion catches it even though the
    // screen would look right either way.
    const sessions = vi
      .spyOn(adminApi, "sessions")
      .mockResolvedValueOnce([session({ id: "s1", owner: "bob" })])
      .mockResolvedValueOnce([session({ id: "s1", owner: "" })]);
    const release = vi.spyOn(adminApi, "releaseSession").mockResolvedValue(undefined);
    render(<Sessions />);
    await screen.findByText(/bob/);
    const callsAfterMount = sessions.mock.calls.length;

    await userEvent.click(screen.getByRole("button", { name: /release/i }));

    expect(release).toHaveBeenCalledWith("s1");
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
    await waitFor(() => expect(sessions.mock.calls.length).toBeGreaterThan(callsAfterMount));
    expect(await screen.findByText("—")).toBeInTheDocument();
  });

  it("shows a confirmation naming the instrument before closing, and sends nothing until confirmed", async () => {
    vi.spyOn(adminApi, "sessions").mockResolvedValue([session({ id: "s1", label: "bench-1" })]);
    const close = vi.spyOn(adminApi, "closeSession").mockResolvedValue(undefined);
    render(<Sessions />);
    await userEvent.click(await screen.findByRole("button", { name: /close/i }));

    const dialog = screen.getByRole("alertdialog");
    expect(dialog).toHaveTextContent(/bench-1/);
    // The listing has no field for "is this session recording" (session_out's
    // `state` is only ever connecting/connected/closed/error), so the warning
    // can't be conditioned on that -- it applies to every close, honestly.
    expect(dialog).toHaveTextContent(/capture in progress/i);
    expect(close).not.toHaveBeenCalled();

    await userEvent.click(within(dialog).getByRole("button", { name: /cancel/i }));
    expect(close).not.toHaveBeenCalled();
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
  });

  it("closes a session only after the confirmation is accepted, and reloads the listing", async () => {
    const sessions = vi
      .spyOn(adminApi, "sessions")
      .mockResolvedValueOnce([session({ id: "s1", label: "bench-1" })])
      .mockResolvedValueOnce([]);
    const close = vi.spyOn(adminApi, "closeSession").mockResolvedValue(undefined);
    render(<Sessions />);
    await screen.findByText(/bench-1/);
    const callsAfterMount = sessions.mock.calls.length;

    await userEvent.click(screen.getByRole("button", { name: /close/i }));
    const dialog = screen.getByRole("alertdialog");
    await userEvent.click(within(dialog).getByRole("button", { name: /close/i }));

    expect(close).toHaveBeenCalledWith("s1");
    await waitFor(() => expect(sessions.mock.calls.length).toBeGreaterThan(callsAfterMount));
    expect(await screen.findByText(/no live sessions/i)).toBeInTheDocument();
  });

  it("reports the server's message when closing fails", async () => {
    vi.spyOn(adminApi, "sessions").mockResolvedValue([session({ id: "s1", label: "bench-1" })]);
    vi.spyOn(adminApi, "closeSession").mockRejectedValue(new Error("session already closing"));
    render(<Sessions />);
    await userEvent.click(await screen.findByRole("button", { name: /close/i }));
    const dialog = screen.getByRole("alertdialog");
    await userEvent.click(within(dialog).getByRole("button", { name: /close/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/session already closing/i);
  });
});
