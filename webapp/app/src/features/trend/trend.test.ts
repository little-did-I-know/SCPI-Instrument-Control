import { beforeEach, describe, expect, it } from "vitest";
import { appendTrend, clearTrend, getTrend, seedTrend, subscribeTrend } from "./trend";

beforeEach(() => clearTrend());

describe("trend buffer", () => {
  it("seeds columns and rows and notifies subscribers", () => {
    let calls = 0;
    const unsubscribe = subscribeTrend(() => { calls += 1; });
    seedTrend({ columns: [{ channel: 1, mtype: "PKPK" }], rows: [[1, 2.5]] });
    unsubscribe();
    expect(getTrend().columns).toEqual([{ channel: 1, mtype: "PKPK" }]);
    expect(getTrend().rows).toEqual([[1, 2.5]]);
    expect(calls).toBe(1);
  });

  it("appends rows mapped into column order, null for missing values", () => {
    seedTrend({ columns: [{ channel: 1, mtype: "PKPK" }, { channel: 2, mtype: "FREQ" }], rows: [] });
    appendTrend(10, [{ channel: 2, mtype: "FREQ", value: 50 }, { channel: 1, mtype: "PKPK", value: 1.5 }]);
    appendTrend(11, [{ channel: 1, mtype: "PKPK", value: null }]);
    expect(getTrend().rows).toEqual([[10, 1.5, 50], [11, null, null]]);
  });

  it("ignores appends before any seed", () => {
    appendTrend(10, [{ channel: 1, mtype: "PKPK", value: 1 }]);
    expect(getTrend().rows).toEqual([]);
  });

  it("drops out-of-order or duplicate timestamps", () => {
    seedTrend({ columns: [{ channel: 1, mtype: "PKPK" }], rows: [[10, 1]] });
    appendTrend(10, [{ channel: 1, mtype: "PKPK", value: 2 }]); // same ts as seeded row: skip
    appendTrend(9, [{ channel: 1, mtype: "PKPK", value: 3 }]); // older: skip
    appendTrend(11, [{ channel: 1, mtype: "PKPK", value: 4 }]);
    expect(getTrend().rows).toEqual([[10, 1], [11, 4]]);
  });
});
