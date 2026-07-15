import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useReferenceSeed } from "./useReferenceSeed";
import { api } from "../../api/client";
import type { ReferenceOverlay } from "../../api/types";
import { clearFrames, getFrame } from "../waveform/frames";
import { useSession } from "../../store/session";

beforeEach(() => {
  useSession.getState().clearSession();
  clearFrames();
});
afterEach(() => vi.restoreAllMocks());

describe("useReferenceSeed", () => {
  it("seeds the overlay from the server on mount", async () => {
    vi.spyOn(api, "getReference").mockResolvedValue({ name: "golden", channel: 1, t0: 0, dt: 1, points: [1, 2] });
    renderHook(() => useReferenceSeed("abc"));
    await waitFor(() => expect(getFrame("REF")?.points).toEqual([1, 2]));
    expect(useSession.getState().activeReference).toEqual({ name: "golden", channel: 1 });
  });

  it("skips a stale response after a live broadcast landed", async () => {
    let resolve!: (v: ReferenceOverlay) => void;
    vi.spyOn(api, "getReference").mockReturnValue(new Promise((r) => { resolve = r; }));
    renderHook(() => useReferenceSeed("abc"));
    act(() => useSession.getState().applyReference({ name: "fresh", channel: 2 }));
    resolve({ name: "stale", channel: 1, t0: 0, dt: 1, points: [9] });
    await new Promise((r) => setTimeout(r, 0));
    expect(useSession.getState().activeReference).toEqual({ name: "fresh", channel: 2 });
    expect(getFrame("REF")).toBeUndefined();
  });
});
