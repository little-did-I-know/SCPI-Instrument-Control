import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LogPanel } from "./LogPanel";
import { clearTrend } from "./trend";
import { ApiError, api } from "../../api/client";
import { setToken } from "../../api/token";
import type { LogInfo } from "../../api/types";
import { useSession } from "../../store/session";

const IDLE: LogInfo = { state: "idle", started_at: null, row_count: 0, columns: [], max_rows: 86400 };
const RECORDING: LogInfo = { state: "recording", started_at: 100, row_count: 0, columns: [{ channel: 1, mtype: "PKPK" }], max_rows: 86400 };

beforeEach(() => {
  clearTrend();
  localStorage.clear();
  useSession.getState().clearSession();
  useSession.getState().setSession({ id: "abc", label: "x", mock: true, address: null, state: "connected", idn: "", model: "", dialect: "legacy", num_channels: 4, viewers: 0, owner: "" });
  vi.spyOn(api, "getLog").mockResolvedValue(IDLE);
  vi.spyOn(api, "getLogData").mockResolvedValue({ columns: [], rows: [] });
});
afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("LogPanel", () => {
  it("seeds status from the server on mount", async () => {
    render(<LogPanel />);
    await waitFor(() => expect(api.getLog).toHaveBeenCalledWith("abc"));
    await waitFor(() => expect(useSession.getState().logStatus?.state).toBe("idle"));
  });

  it("starts a recording", async () => {
    const start = vi.spyOn(api, "logStart").mockResolvedValue(RECORDING);
    render(<LogPanel />);
    await userEvent.click(await screen.findByRole("button", { name: "Start recording" }));
    expect(start).toHaveBeenCalledWith("abc");
  });

  it("stops a recording", async () => {
    const stop = vi.spyOn(api, "logStop").mockResolvedValue(IDLE);
    render(<LogPanel />);
    act(() => useSession.getState().applyLogStatus(RECORDING)); // broadcast landed
    await userEvent.click(await screen.findByRole("button", { name: "Stop recording" }));
    expect(stop).toHaveBeenCalledWith("abc");
  });

  it("enables the CSV download once a recording exists, disabled before", async () => {
    render(<LogPanel />);
    expect(screen.getByText("Download CSV").closest("button")).toBeNull(); // no recording yet: not a button
    act(() => useSession.getState().applyLogStatus(RECORDING));
    await waitFor(() => expect(screen.getByRole("button", { name: "Download CSV" })).toBeInTheDocument());
  });

  it("downloads the trend CSV with the bearer token", async () => {
    setToken("scpi_trend");
    const fetchMock = vi.fn().mockResolvedValue(new Response(new Blob(["data"]), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("URL", { ...URL, createObjectURL: vi.fn(() => "blob:x"), revokeObjectURL: vi.fn() });
    render(<LogPanel />);
    act(() => useSession.getState().applyLogStatus(RECORDING));
    await userEvent.click(await screen.findByRole("button", { name: "Download CSV" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/sessions/abc/scope/log.csv");
    const headers = new Headers(init.headers);
    expect(headers.get("Authorization")).toBe("Bearer scpi_trend");
  });

  it("surfaces a CSV download failure instead of silently doing nothing", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: "Unauthorized", detail: "missing bearer token" }), { status: 401 })));
    render(<LogPanel />);
    act(() => useSession.getState().applyLogStatus(RECORDING));
    await userEvent.click(await screen.findByRole("button", { name: "Download CSV" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("missing bearer token");
  });

  it("surfaces a start error", async () => {
    vi.spyOn(api, "logStart").mockRejectedValue(new ApiError(400, "InvalidParameterError", "no measurements selected"));
    render(<LogPanel />);
    await userEvent.click(await screen.findByRole("button", { name: "Start recording" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("no measurements selected");
  });

  it("backfills the trend buffer on mount so the row counter is live", async () => {
    vi.spyOn(api, "getLog").mockResolvedValue({ state: "idle", started_at: 100, row_count: 2, columns: [{ channel: 1, mtype: "PKPK" }], max_rows: 86400 });
    vi.spyOn(api, "getLogData").mockResolvedValue({ columns: [{ channel: 1, mtype: "PKPK" }], rows: [[100, 1.5], [101, 2.5]] });
    render(<LogPanel />);
    expect(await screen.findByText(/2 rows/)).toBeInTheDocument();
  });
});
