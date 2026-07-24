import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ScopeToolbar } from "./ScopeToolbar";
import { api } from "../../api/client";
import { setToken } from "../../api/token";
import { useSession } from "../../store/session";

const STATE = { run_state: "STOP", timebase: 0.001, channels: { "1": { enabled: true, voltage_scale: 0.5, voltage_offset: 0, coupling: "DC", probe_ratio: 10 } }, trigger: { mode: "AUTO", source: "C1", level: 0, slope: "POS", coupling: "DC" } };

beforeEach(() => {
  localStorage.clear();
  useSession.getState().clearSession();
  useSession.getState().setSession({ id: "abc", label: "x", mock: true, address: null, state: "connected", idn: "", model: "", dialect: "legacy", num_channels: 4, viewers: 0, owner: "" });
  useSession.getState().applyState(STATE);
});
afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("ScopeToolbar", () => {
  it.each([
    ["Run", "run"],
    ["Stop", "stop"],
    ["Single", "single"],
    ["Auto", "auto"],
  ])("%s posts the %s op", async (label, op) => {
    const runOp = vi.spyOn(api, "runOp").mockResolvedValue(STATE);
    render(<ScopeToolbar />);
    await userEvent.click(screen.getByRole("button", { name: label }));
    await waitFor(() => expect(runOp).toHaveBeenCalledWith("abc", op));
  });

  it("shows the run state from the store", () => {
    render(<ScopeToolbar />);
    expect(screen.getByText("STOP")).toBeInTheDocument();
  });

  it("surfaces an ApiError detail", async () => {
    const { ApiError } = await import("../../api/client");
    vi.spyOn(api, "runOp").mockRejectedValue(new ApiError(409, "SessionError", "session abc is error"));
    render(<ScopeToolbar />);
    await userEvent.click(screen.getByRole("button", { name: "Run" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("session abc is error");
  });

  it("downloads the waveform JSON with the bearer token", async () => {
    setToken("scpi_wave");
    const fetchMock = vi.fn().mockResolvedValue(new Response(new Blob(["data"]), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("URL", { ...URL, createObjectURL: vi.fn(() => "blob:x"), revokeObjectURL: vi.fn() });
    render(<ScopeToolbar />);
    await userEvent.click(screen.getByRole("button", { name: "JSON" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/sessions/abc/scope/waveform?channels=1");
    const headers = new Headers(init.headers);
    expect(headers.get("Authorization")).toBe("Bearer scpi_wave");
  });

  it("surfaces a waveform download failure instead of silently doing nothing", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: "Unauthorized", detail: "missing bearer token" }), { status: 401 })));
    render(<ScopeToolbar />);
    await userEvent.click(screen.getByRole("button", { name: "JSON" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("missing bearer token");
  });

  it("returns to disconnected even if the session is already gone (DELETE 404)", async () => {
    const { ApiError } = await import("../../api/client");
    vi.spyOn(api, "deleteSession").mockRejectedValue(new ApiError(404, "HTTPException", "unknown session abc"));
    render(<ScopeToolbar />);
    await userEvent.click(screen.getByRole("button", { name: /disconnect/i }));
    await waitFor(() => expect(useSession.getState().session).toBeNull());
    expect(useSession.getState().status).toBe("disconnected");
  });
});
