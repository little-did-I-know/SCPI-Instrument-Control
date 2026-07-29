import { act, render, screen, waitFor, within } from "@testing-library/react";
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
  recording: false,
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

  it("right-aligns the numeric columns in a mono face", async () => {
    // Viewer counts and idle times are scanned down a column, not read as prose.
    vi.spyOn(adminApi, "sessions").mockResolvedValue([session({ idle_seconds: 5.5 })]);
    render(<Sessions />);
    const cell = await screen.findByText("5.5s idle");
    expect(cell.closest("td")).toHaveStyle({ textAlign: "right" });
  });

  it("keeps the destructive action visually secondary", async () => {
    vi.spyOn(adminApi, "sessions").mockResolvedValue([session()]);
    render(<Sessions />);
    const close = await screen.findByRole("button", { name: "Close" });
    const release = screen.getByRole("button", { name: "Release" });
    expect(close).toHaveAttribute("data-variant", "danger");
    expect(release).not.toHaveAttribute("data-variant", "danger");
  });

  it("explains an empty list rather than just stating it", async () => {
    vi.spyOn(adminApi, "sessions").mockResolvedValue([]);
    render(<Sessions />);
    expect(await screen.findByText(/Sessions appear here when someone opens an instrument/)).toBeInTheDocument();
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
    vi.spyOn(adminApi, "sessions").mockResolvedValue([session({ id: "s1", label: "bench-1", recording: false })]);
    const close = vi.spyOn(adminApi, "closeSession").mockResolvedValue(undefined);
    render(<Sessions />);
    await userEvent.click(await screen.findByRole("button", { name: /close/i }));

    const dialog = screen.getByRole("alertdialog");
    expect(dialog).toHaveTextContent(/bench-1/);
    expect(close).not.toHaveBeenCalled();

    await userEvent.click(within(dialog).getByRole("button", { name: /cancel/i }));
    expect(close).not.toHaveBeenCalled();
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
  });

  it("warns that the session is recording when it is", async () => {
    // Backed by /api/sessions' `recording` field (admin/api.py::_is_recording),
    // which mirrors the same recorder.state == "recording" comparison used by
    // api/scope.py and adapters.py -- not a new notion of recording.
    vi.spyOn(adminApi, "sessions").mockResolvedValue([session({ id: "s1", label: "bench-1", recording: true })]);
    render(<Sessions />);
    await userEvent.click(await screen.findByRole("button", { name: /close/i }));
    expect(screen.getByRole("alertdialog")).toHaveTextContent(/recording/i);
  });

  it("does not warn about recording when the session is not recording", async () => {
    // Asserting only the positive branch would let a hardcoded warning pass.
    vi.spyOn(adminApi, "sessions").mockResolvedValue([session({ id: "s1", label: "bench-1", recording: false })]);
    render(<Sessions />);
    await userEvent.click(await screen.findByRole("button", { name: /close/i }));
    expect(screen.getByRole("alertdialog")).not.toHaveTextContent(/recording/i);
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

  it("leaves other rows usable while one row is releasing", async () => {
    // The old code disabled every button on every row whenever any action was in
    // flight, so acting on one bench greyed out the whole panel.
    vi.spyOn(adminApi, "sessions").mockResolvedValue([
      session({ id: "aaa", label: "bench-a" }),
      session({ id: "bbb", label: "bench-b" }),
    ]);
    let resolveRelease: () => void = () => {};
    vi.spyOn(adminApi, "releaseSession").mockReturnValue(
      new Promise<void>((resolve) => {
        resolveRelease = resolve;
      }),
    );
    render(<Sessions />);

    const rows = await screen.findAllByRole("row");
    const rowA = within(rows[1]);
    const rowB = within(rows[2]);
    await userEvent.click(rowA.getByRole("button", { name: "Release" }));

    expect(rowA.getByRole("button", { name: "Release" })).toBeDisabled();
    expect(rowB.getByRole("button", { name: "Release" })).toBeEnabled();
    expect(rowB.getByRole("button", { name: "Close" })).toBeEnabled();

    resolveRelease();
  });

  it("puts the close confirmation in a modal that traps focus", async () => {
    vi.spyOn(adminApi, "sessions").mockResolvedValue([session({ id: "aaa", label: "bench-a" })]);
    const close = vi.spyOn(adminApi, "closeSession").mockResolvedValue(undefined);
    render(<Sessions />);
    await userEvent.click(await screen.findByRole("button", { name: "Close" }));

    const dialog = screen.getByRole("alertdialog");
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(screen.getByRole("button", { name: "Cancel" })).toHaveFocus();
    expect(close).not.toHaveBeenCalled();

    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
    expect(close).not.toHaveBeenCalled();
  });

  it("refreshes on a timer so the idle column cannot go stale", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      vi.spyOn(adminApi, "sessions")
        .mockResolvedValueOnce([session({ idle_seconds: 4 })])
        .mockResolvedValueOnce([session({ idle_seconds: 14 })]);
      render(<Sessions />);
      expect(await screen.findByText("4s idle")).toBeInTheDocument();

      await act(async () => {
        await vi.advanceTimersByTimeAsync(10_000);
      });

      expect(await screen.findByText("14s idle")).toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });

  it("does not refresh while a confirmation is open", async () => {
    // The list must not reshuffle under a confirmation the operator is reading.
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      const list = vi.spyOn(adminApi, "sessions").mockResolvedValue([session({ id: "aaa", label: "bench-a" })]);
      render(<Sessions />);
      await userEvent.click(await screen.findByRole("button", { name: "Close" }));
      const callsWhenOpened = list.mock.calls.length;

      await act(async () => {
        await vi.advanceTimersByTimeAsync(60_000);
      });

      expect(list.mock.calls.length).toBe(callsWhenOpened);
    } finally {
      vi.useRealTimers();
    }
  });

  it("keeps the last good rows when a refresh fails", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      vi.spyOn(adminApi, "sessions")
        .mockResolvedValueOnce([session({ label: "bench-a" })])
        .mockRejectedValueOnce(new Error("gateway unreachable"));
      render(<Sessions />);
      expect(await screen.findByText(/bench-a/)).toBeInTheDocument();

      await act(async () => {
        await vi.advanceTimersByTimeAsync(10_000);
      });

      expect(await screen.findByRole("alert")).toHaveTextContent("gateway unreachable");
      expect(screen.getByText(/bench-a/)).toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });

  it("stops polling once unmounted", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      const list = vi.spyOn(adminApi, "sessions").mockResolvedValue([session()]);
      const { unmount } = render(<Sessions />);
      await screen.findByRole("table");
      unmount();
      const callsAtUnmount = list.mock.calls.length;

      await act(async () => {
        await vi.advanceTimersByTimeAsync(60_000);
      });

      expect(list.mock.calls.length).toBe(callsAtUnmount);
    } finally {
      vi.useRealTimers();
    }
  });

  it("does not let a stale poll response overwrite a newer release reload", async () => {
    // A release fires its own reload; if an in-flight poll tick's older
    // response resolves after it, the released session must not reappear.
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      let resolvePoll: (rows: SessionRow[]) => void = () => {};
      let resolveReleaseReload: (rows: SessionRow[]) => void = () => {};
      const list = vi
        .spyOn(adminApi, "sessions")
        .mockResolvedValueOnce([session({ id: "aaa", label: "bench-a", owner: "bob" })])
        // The poll tick's request, kicked off while the release is in flight.
        .mockImplementationOnce(
          () => new Promise<SessionRow[]>((resolve) => (resolvePoll = resolve)),
        )
        // The release's own reload, requested after the poll tick above.
        .mockImplementationOnce(
          () => new Promise<SessionRow[]>((resolve) => (resolveReleaseReload = resolve)),
        );
      vi.spyOn(adminApi, "releaseSession").mockResolvedValue(undefined);
      render(<Sessions />);
      await screen.findByText(/bob/);

      // Trigger the poll tick: its request goes in flight but does not resolve yet.
      await act(async () => {
        await vi.advanceTimersByTimeAsync(10_000);
      });
      expect(list.mock.calls.length).toBe(2);

      // Now release, which fires its own (third) reload request.
      await user.click(screen.getByRole("button", { name: "Release" }));
      await vi.waitFor(() => expect(list.mock.calls.length).toBe(3));

      // The release's reload resolves first, clearing the owner...
      await act(async () => {
        resolveReleaseReload([session({ id: "aaa", label: "bench-a", owner: "" })]);
      });
      expect(await screen.findByText("—")).toBeInTheDocument();

      // ...then the stale poll response resolves late, with the old owner.
      // It must be discarded rather than winning because it landed last.
      await act(async () => {
        resolvePoll([session({ id: "aaa", label: "bench-a", owner: "bob" })]);
      });
      expect(screen.getByText("—")).toBeInTheDocument();
      expect(screen.queryByText(/bob/)).not.toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });
});
