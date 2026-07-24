import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, api } from "./client";
import { clearToken, setToken } from "./token";

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

beforeEach(() => clearToken());

afterEach(() => vi.unstubAllGlobals());

describe("api client", () => {
  it("creates a mock session", async () => {
    const fetchMock = mockFetch({ id: "abc", label: "Mock scope", mock: true, address: null, state: "connected", idn: "x", model: "SDS1104X-E", dialect: "legacy", num_channels: 4, viewers: 0 }, { status: 201 });
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

  it("attaches the stored token as a bearer header", async () => {
    setToken("scpi_abc123");
    const fetchMock = mockFetch({ run_state: "TRIGD", timebase: 0.001, channels: {}, trigger: { mode: "AUTO", source: null, level: null, slope: null, coupling: null } });
    await api.runOp("abc", "single");
    const [, init] = fetchMock.mock.calls[0];
    const headers = new Headers(init.headers);
    expect(headers.get("Authorization")).toBe("Bearer scpi_abc123");
  });

  it("omits the Authorization header when no token is stored", async () => {
    const fetchMock = mockFetch({ run_state: "TRIGD", timebase: 0.001, channels: {}, trigger: { mode: "AUTO", source: null, level: null, slope: null, coupling: null } });
    await api.runOp("abc", "single");
    const [, init] = fetchMock.mock.calls[0];
    const headers = new Headers(init.headers);
    expect(headers.has("Authorization")).toBe(false);
  });

  it("preserves the JSON Content-Type header alongside the bearer token", async () => {
    setToken("scpi_abc123");
    const fetchMock = mockFetch({ id: "abc", label: "Mock scope", mock: true, address: null, state: "connected", idn: "x", model: "SDS1104X-E", dialect: "legacy", num_channels: 4, viewers: 0 }, { status: 201 });
    await api.createSession({ mock: true });
    const [, init] = fetchMock.mock.calls[0];
    const headers = new Headers(init.headers);
    expect(headers.get("Content-Type")).toBe("application/json");
    expect(headers.get("Authorization")).toBe("Bearer scpi_abc123");
  });
});
