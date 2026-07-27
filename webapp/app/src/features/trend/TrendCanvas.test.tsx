import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { TrendCanvas, formatElapsed, seriesStats, trendSeriesPixels } from "./TrendCanvas";
import { clearTrend } from "./trend";
import { api } from "../../api/client";
import { useSession } from "../../store/session";

beforeEach(() => {
  clearTrend();
  useSession.getState().clearSession();
  useSession.getState().setSession({ id: "abc", label: "x", mock: true, address: null, state: "connected", idn: "", model: "", dialect: "legacy", num_channels: 4, viewers: 0, owner: "", kind: "scope" });
});
afterEach(() => vi.restoreAllMocks());

describe("trendSeriesPixels", () => {
  it("maps time to x and min/max to the vertical margins, skipping nulls", () => {
    const rows: (number | null)[][] = [[0, 0], [5, null], [10, 10]];
    const px = trendSeriesPixels(rows, 0, 100, 100, 0);
    expect(px).toHaveLength(2); // null sample skipped
    expect(px[0].x).toBeCloseTo(0);
    expect(px[1].x).toBeCloseTo(100);
    expect(px[0].y).toBeCloseTo(95); // min -> bottom margin
    expect(px[1].y).toBeCloseTo(5); // max -> top margin
  });

  it("handles a flat series without dividing by zero", () => {
    const px = trendSeriesPixels([[0, 3], [10, 3]], 0, 100, 100, 0);
    expect(px.every((p) => Number.isFinite(p.y))).toBe(true);
  });
});

describe("seriesStats", () => {
  it("reports latest, min, and max ignoring nulls", () => {
    const rows: (number | null)[][] = [[0, 5], [1, null], [2, 1], [3, 3]];
    expect(seriesStats(rows, 0)).toEqual({ latest: 3, min: 1, max: 5 });
  });

  it("is all-null for an empty column", () => {
    expect(seriesStats([[0, null]], 0)).toEqual({ latest: null, min: null, max: null });
  });
});

describe("formatElapsed", () => {
  it("scales units", () => {
    expect(formatElapsed(45)).toBe("45s");
    expect(formatElapsed(125)).toBe("2m 05s");
    expect(formatElapsed(3725)).toBe("1h 02m 05s");
  });
});

describe("TrendCanvas", () => {
  it("shows the empty state and backfills from the server on mount", async () => {
    const getLogData = vi.spyOn(api, "getLogData").mockResolvedValue({ columns: [], rows: [] });
    render(<TrendCanvas />);
    expect(screen.getByText(/no recording yet/i)).toBeInTheDocument();
    await waitFor(() => expect(getLogData).toHaveBeenCalledWith("abc"));
  });

  it("renders a canvas and legend without throwing when data exists", async () => {
    vi.spyOn(api, "getLogData").mockResolvedValue({ columns: [{ channel: 1, mtype: "PKPK" }], rows: [[100, 1.5], [101, 2.5]] });
    render(<TrendCanvas />);
    expect(await screen.findByText("C1 PKPK")).toBeInTheDocument(); // legend entry from the seeded data
  });
});
