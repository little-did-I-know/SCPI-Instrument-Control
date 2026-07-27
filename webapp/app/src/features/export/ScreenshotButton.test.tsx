import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ScreenshotButton } from "./ScreenshotButton";
import { setToken } from "../../api/token";
import { useSession } from "../../store/session";

beforeEach(() => {
  localStorage.clear();
  useSession.getState().clearSession();
});
afterEach(() => vi.unstubAllGlobals());

describe("ScreenshotButton", () => {
  it("downloads the screenshot URL with the bearer token when connected", async () => {
    useSession.getState().setSession({ id: "abc", label: "x", mock: true, address: null, state: "connected", idn: "", model: "", dialect: "legacy", num_channels: 4, viewers: 0, owner: "", kind: "scope" });
    setToken("scpi_shot");
    const fetchMock = vi.fn().mockResolvedValue(new Response(new Blob(["data"]), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("URL", { ...URL, createObjectURL: vi.fn(() => "blob:x"), revokeObjectURL: vi.fn() });

    render(<ScreenshotButton />);
    await userEvent.click(screen.getByRole("button", { name: /screenshot/i }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/sessions/abc/scope/screenshot.png");
    const headers = new Headers(init.headers);
    expect(headers.get("Authorization")).toBe("Bearer scpi_shot");
  });

  it("is not a button with no session", () => {
    render(<ScreenshotButton />);
    expect(screen.getByText(/screenshot/i).closest("button")).toBeNull();
  });

  it("surfaces a download failure instead of silently doing nothing", async () => {
    useSession.getState().setSession({ id: "abc", label: "x", mock: true, address: null, state: "connected", idn: "", model: "", dialect: "legacy", num_channels: 4, viewers: 0, owner: "", kind: "scope" });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: "Unauthorized", detail: "missing bearer token" }), { status: 401 })));

    render(<ScreenshotButton />);
    await userEvent.click(screen.getByRole("button", { name: /screenshot/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent("missing bearer token");
  });
});
