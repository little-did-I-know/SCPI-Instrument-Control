import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, api } from "./client";

function mockFetch(body: unknown, init: { status?: number } = {}) {
  const status = init.status ?? 200;
  const fetchMock = vi.fn().mockResolvedValue({
    ok: status < 400,
    status,
    json: async () => body,
    text: async () => JSON.stringify(body),
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => vi.unstubAllGlobals());

describe("api client", () => {
  it("creates a mock session", async () => {
    const fetchMock = mockFetch({ id: "abc", label: "Mock scope", mock: true, address: null, state: "connected", idn: "x", model: "SDS1104X-E", dialect: "legacy", num_channels: 4 }, { status: 201 });
    const session = await api.createSession({ mock: true });
    expect(session.id).toBe("abc");
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/sessions");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({ mock: true });
  });

  it("throws ApiError carrying the server error shape", async () => {
    mockFetch({ error: "InvalidParameterError", detail: "invalid coupling: BANANA" }, { status: 400 });
    await expect(api.patchChannel("abc", 1, { coupling: "BANANA" })).rejects.toMatchObject({
      status: 400,
      error: "InvalidParameterError",
      detail: "invalid coupling: BANANA",
    });
    await expect(api.patchChannel("abc", 1, { coupling: "BANANA" })).rejects.toBeInstanceOf(ApiError);
  });

  it("builds a capture URL with the channel list", () => {
    expect(api.captureUrl("abc", [1, 2])).toBe("/api/sessions/abc/scope/capture.csv?channels=1,2");
  });

  it("sends run ops as POST", async () => {
    const fetchMock = mockFetch({ run_state: "TRIGD", timebase: 0.001, channels: {}, trigger: { mode: "AUTO", source: null, level: null, slope: null, coupling: null } });
    await api.runOp("abc", "single");
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/sessions/abc/scope/single");
    expect(init.method).toBe("POST");
  });
});
