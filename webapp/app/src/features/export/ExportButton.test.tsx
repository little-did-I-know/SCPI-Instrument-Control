import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ExportButton } from "./ExportButton";
import { setToken } from "../../api/token";
import { useSession } from "../../store/session";

const BASE = { run_state: "STOP", timebase: 0.001, trigger: { mode: "AUTO", source: "C1", level: 0, slope: "POS", coupling: "DC" } };

beforeEach(() => {
  localStorage.clear();
  useSession.getState().clearSession();
  useSession.getState().setSession({ id: "abc", label: "x", mock: true, address: null, state: "connected", idn: "", model: "", dialect: "legacy", num_channels: 4, viewers: 0, owner: "" });
});
afterEach(() => vi.unstubAllGlobals());

describe("ExportButton", () => {
  it("downloads the capture URL for enabled channels only, with the bearer token", async () => {
    useSession.getState().applyState({
      ...BASE,
      channels: {
        "1": { enabled: true, voltage_scale: 1, voltage_offset: 0, coupling: "DC", probe_ratio: 1 },
        "2": { enabled: false, voltage_scale: 1, voltage_offset: 0, coupling: "DC", probe_ratio: 1 },
        "3": { enabled: true, voltage_scale: 1, voltage_offset: 0, coupling: "DC", probe_ratio: 1 },
      },
    });
    setToken("scpi_export");
    const fetchMock = vi.fn().mockResolvedValue(new Response(new Blob(["data"]), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("URL", { ...URL, createObjectURL: vi.fn(() => "blob:x"), revokeObjectURL: vi.fn() });

    render(<ExportButton />);
    await userEvent.click(screen.getByRole("button", { name: /export csv/i }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/sessions/abc/scope/capture.csv?channels=1,3");
    const headers = new Headers(init.headers);
    expect(headers.get("Authorization")).toBe("Bearer scpi_export");
  });

  it("is disabled when no channel is enabled", () => {
    useSession.getState().applyState({ ...BASE, channels: { "1": { enabled: false, voltage_scale: 1, voltage_offset: 0, coupling: "DC", probe_ratio: 1 } } });
    render(<ExportButton />);
    expect(screen.getByText(/export csv/i).closest("button")).toBeNull();
  });

  it("surfaces a download failure instead of silently doing nothing", async () => {
    useSession.getState().applyState({ ...BASE, channels: { "1": { enabled: true, voltage_scale: 1, voltage_offset: 0, coupling: "DC", probe_ratio: 1 } } });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: "Unauthorized", detail: "missing bearer token" }), { status: 401 })));

    render(<ExportButton />);
    await userEvent.click(screen.getByRole("button", { name: /export csv/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent("missing bearer token");
  });
});
