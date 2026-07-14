import { beforeEach, describe, expect, it } from "vitest";
import { getRecent, pushRecent, RECENT_KEY } from "./recent";

beforeEach(() => localStorage.clear());

const entry = (address: string | null, model = "SDS824X HD") => ({ address, label: model, kind: "scope", model, mock: address === null });

describe("recent", () => {
  it("returns [] when nothing stored or storage is corrupt", () => {
    expect(getRecent()).toEqual([]);
    localStorage.setItem(RECENT_KEY, "not json");
    expect(getRecent()).toEqual([]);
  });

  it("pushes most-recent-first and dedups by address", () => {
    pushRecent(entry("192.168.1.50"));
    pushRecent(entry("192.168.1.51", "SDS1104X-E"));
    pushRecent(entry("192.168.1.50")); // re-use bumps to front, no dup
    const list = getRecent();
    expect(list.map((r) => r.address)).toEqual(["192.168.1.50", "192.168.1.51"]);
  });

  it("dedups the mock entry by mock flag, not address", () => {
    pushRecent(entry(null));
    pushRecent(entry(null));
    expect(getRecent().filter((r) => r.mock)).toHaveLength(1);
  });

  it("caps at 5 entries", () => {
    for (let i = 0; i < 8; i += 1) pushRecent(entry("10.0.0." + i));
    expect(getRecent()).toHaveLength(5);
    expect(getRecent()[0].address).toBe("10.0.0.7");
  });
});
