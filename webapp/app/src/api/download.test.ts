import { beforeEach, describe, expect, it, vi } from "vitest";
import { downloadAuthenticated } from "./download";
import { setToken, clearToken } from "./token";

describe("downloadAuthenticated", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it("sends the bearer token with the request", async () => {
    setToken("scpi_dl");
    const fetchMock = vi.fn().mockResolvedValue(new Response(new Blob(["data"]), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("URL", { ...URL, createObjectURL: vi.fn(() => "blob:x"), revokeObjectURL: vi.fn() });
    await downloadAuthenticated("/api/thing.csv", "thing.csv");
    const headers = new Headers(fetchMock.mock.calls[0][1].headers);
    expect(headers.get("Authorization")).toBe("Bearer scpi_dl");
  });

  it("throws ApiError on a 401 instead of downloading an error page", async () => {
    clearToken();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: "Unauthorized", detail: "no token" }), { status: 401 })));
    await expect(downloadAuthenticated("/api/thing.csv", "thing.csv")).rejects.toThrow();
  });

  it("revokes the object URL after triggering the download", async () => {
    setToken("scpi_dl");
    const revoke = vi.fn();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(new Blob(["data"]), { status: 200 })));
    vi.stubGlobal("URL", { ...URL, createObjectURL: vi.fn(() => "blob:x"), revokeObjectURL: revoke });
    await downloadAuthenticated("/api/thing.csv", "thing.csv");
    expect(revoke).toHaveBeenCalledWith("blob:x");
  });
});
