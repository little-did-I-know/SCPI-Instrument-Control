import { beforeEach, describe, expect, it } from "vitest";
import { captureTokenFromUrl, clearToken, getToken, setToken } from "./token";

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
