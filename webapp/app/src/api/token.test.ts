import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { captureTokenFromUrl, clearToken, getToken, redeemInviteFromUrl, setToken } from "./token";

describe("token storage", () => {
  beforeEach(() => {
    localStorage.clear();
    window.history.replaceState({}, "", "/");
  });

  it("round-trips a token", () => {
    setToken("scpi_abc");
    expect(getToken()).toBe("scpi_abc");
  });

  it("returns null when unset", () => {
    expect(getToken()).toBeNull();
  });

  it("clears a token", () => {
    setToken("scpi_abc");
    clearToken();
    expect(getToken()).toBeNull();
  });

  it("captures a token from the URL and strips it", () => {
    window.history.replaceState({}, "", "/?token=scpi_fromurl");
    captureTokenFromUrl();
    expect(getToken()).toBe("scpi_fromurl");
    expect(window.location.search).not.toContain("token");
  });

  it("leaves an existing token alone when the URL has none", () => {
    setToken("scpi_existing");
    captureTokenFromUrl();
    expect(getToken()).toBe("scpi_existing");
  });
});

describe("invitation redemption", () => {
  beforeEach(() => {
    localStorage.clear();
    window.history.replaceState({}, "", "/");
    vi.restoreAllMocks();
  });

  afterEach(() => vi.unstubAllGlobals());

  it("redeems an invite from the URL and stores the token", async () => {
    window.history.replaceState({}, "", "/?invite=abc123");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ token: "scpi_new", identity: "bob" }), { status: 200 })));
    await redeemInviteFromUrl();
    expect(getToken()).toBe("scpi_new");
  });

  it("strips the invite from the URL", async () => {
    window.history.replaceState({}, "", "/?invite=abc123");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ token: "scpi_new", identity: "bob" }), { status: 200 })));
    await redeemInviteFromUrl();
    expect(window.location.search).not.toContain("invite");
  });

  it("strips the invite before the request resolves", async () => {
    // The credential must leave the address bar immediately, not once the
    // gateway answers. If the request hangs, a stripped-on-success
    // implementation leaves the invite sitting in history and in the
    // Referer of the next link the user clicks.
    window.history.replaceState({}, "", "/?invite=abc123");
    let release: (value: Response) => void = () => {};
    vi.stubGlobal("fetch", vi.fn().mockReturnValue(new Promise<Response>((resolve) => { release = resolve; })));
    const pending = redeemInviteFromUrl();
    expect(window.location.search).not.toContain("invite");
    release(new Response(JSON.stringify({ token: "scpi_new", identity: "bob" }), { status: 200 }));
    await pending;
  });

  it("strips the invite even when the gateway rejects it", async () => {
    window.history.replaceState({}, "", "/?invite=expired");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: "HTTPException", detail: "no" }), { status: 401 })));
    await redeemInviteFromUrl();
    expect(window.location.search).not.toContain("invite");
    expect(getToken()).toBeNull();
  });

  it("survives an unreachable gateway", async () => {
    window.history.replaceState({}, "", "/?invite=abc123");
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("network down")));
    await expect(redeemInviteFromUrl()).resolves.toBeUndefined();
    expect(getToken()).toBeNull();
  });

  it("preserves other query parameters", async () => {
    window.history.replaceState({}, "", "/?invite=abc123&debug=1");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ token: "scpi_new", identity: "bob" }), { status: 200 })));
    await redeemInviteFromUrl();
    expect(window.location.search).toContain("debug=1");
  });

  it("does nothing when the URL carries no invite", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    setToken("scpi_existing");
    await redeemInviteFromUrl();
    expect(fetchMock).not.toHaveBeenCalled();
    expect(getToken()).toBe("scpi_existing");
  });
});
