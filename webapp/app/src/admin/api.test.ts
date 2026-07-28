import { beforeEach, describe, expect, it, vi } from "vitest";
import { adminApi } from "./api";

describe("adminApi", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("lists identities", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify([{ name: "bob", devices: 2, last_used: null }]), { status: 200 })));
    await expect(adminApi.identities()).resolves.toEqual([{ name: "bob", devices: 2, last_used: null }]);
  });

  it("sends no Authorization header", async () => {
    // The admin app has no auth. Sending a bearer token would be harmless but
    // misleading -- it would imply a credential model that does not exist.
    const fetchMock = vi.fn().mockResolvedValue(new Response("[]", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    await adminApi.identities();
    const headers = new Headers(fetchMock.mock.calls[0][1]?.headers ?? {});
    expect(headers.get("authorization")).toBeNull();
  });

  it("surfaces the server's message on failure", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: "HTTPException", detail: "no identity named 'ghost'" }), { status: 404 })));
    await expect(adminApi.revokeIdentity("ghost")).rejects.toThrow(/ghost/);
  });

  it("cancels by id, never by code", async () => {
    // A code in the URL path lands in the host's access log. The id exists to
    // keep it out.
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);
    await adminApi.cancelInvitation("a1b2c3d4");
    expect(fetchMock.mock.calls[0][0]).toBe("/api/invitations/a1b2c3d4");
  });
});
