import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MeasurePanel } from "./MeasurePanel";
import { api } from "../../api/client";
import { useSession } from "../../store/session";

const STATE = { run_state: "STOP", timebase: 0.001, channels: { "1": { enabled: true, voltage_scale: 0.5, voltage_offset: 0, coupling: "DC", probe_ratio: 10 } }, trigger: { mode: "AUTO", source: "C1", level: 0, slope: "POS", coupling: "DC" } };

beforeEach(() => {
  useSession.getState().clearSession();
  useSession.getState().setSession({ id: "abc", label: "x", mock: true, address: null, state: "connected", idn: "", model: "", dialect: "legacy", num_channels: 4, viewers: 0 });
  useSession.getState().applyState(STATE);
});
afterEach(() => vi.restoreAllMocks());

describe("MeasurePanel", () => {
  it("PUTs the selected measurement list", async () => {
    const setMeasurements = vi.spyOn(api, "setMeasurements").mockResolvedValue({ measurements: [{ channel: 1, mtype: "PKPK" }] });
    render(<MeasurePanel />);

    await userEvent.click(screen.getByLabelText("PKPK C1"));

    await waitFor(() => expect(setMeasurements).toHaveBeenCalledWith("abc", [{ channel: 1, mtype: "PKPK" }]));
  });

  it("renders streamed values and shows -- for nulls", () => {
    // values stream only supplies readouts now — the row is only shown for a SELECTED
    // measurement, so the selection must also be seeded via measurementConfig.
    useSession.getState().applyMeasurementConfig([
      { channel: 1, mtype: "PKPK" },
      { channel: 1, mtype: "FREQ" },
    ]);
    useSession.getState().applyMeasurements([
      { channel: 1, mtype: "PKPK", value: 2.5 },
      { channel: 1, mtype: "FREQ", value: null },
    ]);
    render(<MeasurePanel />);

    expect(screen.getByText("2.500")).toBeInTheDocument();
    expect(screen.getByText("--")).toBeInTheDocument();
  });

  it("keeps the server's selection after a remount instead of re-seeding stale local state", async () => {
    const setMeasurements = vi.spyOn(api, "setMeasurements").mockResolvedValue({ measurements: [] });
    // server truth: PKPK C1 is already active and streaming (measurementConfig carries the
    // selection; measurements carries the streamed value alongside it)
    useSession.getState().applyMeasurementConfig([{ channel: 1, mtype: "PKPK" }]);
    useSession.getState().applyMeasurements([{ channel: 1, mtype: "PKPK", value: 2.5 }]);

    const view = render(<MeasurePanel />);
    expect(screen.getByLabelText("PKPK C1")).toBeInTheDocument();

    // simulate a rail-tab switch away and back
    view.unmount();
    render(<MeasurePanel />);

    // now toggle a DIFFERENT measurement — the PUT must preserve the server's existing PKPK C1
    await userEvent.click(screen.getByLabelText("FREQ C1"));

    await waitFor(() =>
      expect(setMeasurements).toHaveBeenCalledWith("abc", [
        { channel: 1, mtype: "PKPK" },
        { channel: 1, mtype: "FREQ" },
      ]),
    );
  });

  // The remount test above only exercises the seed path (the store is already correct at mount).
  // The selection must track the store on EVERY render: a measurement that arrives on the stream
  // while the panel stays mounted must survive the next toggle's full-replacement PUT.
  it("computes the PUT from the server's latest list, not a local mirror captured at mount", async () => {
    const setMeasurements = vi.spyOn(api, "setMeasurements").mockResolvedValue({ measurements: [] });
    render(<MeasurePanel />); // store starts with no measurements

    // server truth arrives after mount (restored session / another client / late broadcast) —
    // a measurements_config broadcast is what actually changes the selection.
    act(() => {
      useSession.getState().applyMeasurementConfig([{ channel: 1, mtype: "PKPK" }]);
      useSession.getState().applyMeasurements([{ channel: 1, mtype: "PKPK", value: 2.5 }]);
    });

    await userEvent.click(screen.getByLabelText("FREQ C1"));

    await waitFor(() =>
      expect(setMeasurements).toHaveBeenCalledWith("abc", [
        { channel: 1, mtype: "PKPK" },
        { channel: 1, mtype: "FREQ" },
      ]),
    );
  });

  // The backend only broadcasts measurements when its list is NON-empty
  // (sessions.py: `if self.measurements and self._poll_count % N == 0`), so after deselecting
  // everything the store keeps the last streamed values forever. Falling back to the store
  // would re-check the box and resurrect the measurement on the next PUT.
  it("deselecting the last measurement stays deselected (server never broadcasts an empty list)", async () => {
    const setMeasurements = vi
      .spyOn(api, "setMeasurements")
      .mockResolvedValueOnce({ measurements: [{ channel: 1, mtype: "PKPK" }] })
      .mockResolvedValueOnce({ measurements: [] });
    render(<MeasurePanel />);

    await userEvent.click(screen.getByLabelText("PKPK C1"));
    await waitFor(() => expect(setMeasurements).toHaveBeenCalledWith("abc", [{ channel: 1, mtype: "PKPK" }]));

    // the stream delivers a value for the active measurement
    act(() => useSession.getState().applyMeasurements([{ channel: 1, mtype: "PKPK", value: 2.5 }]));

    // now uncheck it — this must PUT [] and STAY unchecked
    await userEvent.click(screen.getByLabelText("PKPK C1"));
    await waitFor(() => expect(setMeasurements).toHaveBeenLastCalledWith("abc", []));

    // and a subsequent selection must NOT resurrect PKPK
    setMeasurements.mockResolvedValueOnce({ measurements: [{ channel: 1, mtype: "FREQ" }] });
    await userEvent.click(screen.getByLabelText("FREQ C1"));
    await waitFor(() => expect(setMeasurements).toHaveBeenLastCalledWith("abc", [{ channel: 1, mtype: "FREQ" }]));
  });

  // Racing toggles: a slow PUT must not settle the selection after a newer toggle is in flight.
  // Deterministic — the first response is resolved by hand, no timers.
  it("a stale PUT response does not clobber a newer in-flight toggle", async () => {
    type Ack = { measurements: { channel: number; mtype: string }[] };
    let resolveFirst!: (value: Ack) => void;
    const first = new Promise<Ack>((resolve) => { resolveFirst = resolve; });
    const second = new Promise<Ack>(() => {}); // still in flight for the whole test

    const setMeasurements = vi
      .spyOn(api, "setMeasurements")
      .mockReturnValueOnce(first)
      .mockReturnValueOnce(second)
      .mockResolvedValue({ measurements: [] });
    render(<MeasurePanel />);

    await userEvent.click(screen.getByLabelText("PKPK C1")); // PUT #1 — slow
    await userEvent.click(screen.getByLabelText("FREQ C1")); // PUT #2 — supersedes it
    await waitFor(() =>
      expect(setMeasurements).toHaveBeenLastCalledWith("abc", [
        { channel: 1, mtype: "PKPK" },
        { channel: 1, mtype: "FREQ" },
      ]),
    );

    // PUT #1 lands late, echoing only PKPK. It is stale and must be ignored — if it settles the
    // selection, both boxes flap to unchecked and the next click drops PKPK *and* FREQ.
    await act(async () => { resolveFirst({ measurements: [{ channel: 1, mtype: "PKPK" }] }); });

    await userEvent.click(screen.getByLabelText("MEAN C1"));
    await waitFor(() =>
      expect(setMeasurements).toHaveBeenLastCalledWith("abc", [
        { channel: 1, mtype: "PKPK" },
        { channel: 1, mtype: "FREQ" },
        { channel: 1, mtype: "MEAN" },
      ]),
    );
  });

  it("loads the current selection from the server on mount", async () => {
    vi.spyOn(api, "getMeasurements").mockResolvedValue({ measurements: [{ channel: 1, mtype: "PKPK" }] });
    render(<MeasurePanel />);
    // PKPK C1 shows as checked once the GET resolves (query the checkbox by name and assert the PUT would drop it)
    const setMeasurements = vi.spyOn(api, "setMeasurements").mockResolvedValue({ measurements: [] });
    await waitFor(() => expect(api.getMeasurements).toHaveBeenCalledWith("abc"));
    await userEvent.click(await screen.findByLabelText("PKPK C1")); // was selected → unchecking PUTs []
    await waitFor(() => expect(setMeasurements).toHaveBeenLastCalledWith("abc", []));
  });

  it("reconciles a measurements_config broadcast into the selection", async () => {
    // this covers the broadcast-BEFORE-GET-settles path: the broadcast lands while the mocked
    // GET is still in flight, so the noBroadcastSince guard must block the GET from clobbering it.
    vi.spyOn(api, "getMeasurements").mockResolvedValue({ measurements: [] });
    render(<MeasurePanel />);
    act(() => useSession.getState().applyMeasurementConfig([{ channel: 1, mtype: "FREQ" }]));
    const setMeasurements = vi.spyOn(api, "setMeasurements").mockResolvedValue({ measurements: [] });
    await userEvent.click(await screen.findByLabelText("FREQ C1")); // config made it selected → unchecking PUTs []
    await waitFor(() => expect(setMeasurements).toHaveBeenLastCalledWith("abc", []));
  });

  it("reflects a measurements_config broadcast that arrives after the mount GET settled (live cross-tab sync)", async () => {
    vi.spyOn(api, "getMeasurements").mockResolvedValue({ measurements: [{ channel: 1, mtype: "PKPK" }] });
    render(<MeasurePanel />);
    // GET settles FIRST — PKPK is the acknowledged selection (this is steady state, not the race window)
    await waitFor(() => expect(api.getMeasurements).toHaveBeenCalledWith("abc"));
    await screen.findByLabelText("PKPK C1");
    // a broadcast from another tab now changes the selection to FREQ, AFTER the GET already settled
    act(() => useSession.getState().applyMeasurementConfig([{ channel: 1, mtype: "FREQ" }]));
    // the panel must reflect FREQ live: clicking the now-selected FREQ unchecks it → PUT [].
    // (Old acked-mask design would still show PKPK selected, so clicking FREQ would PUT [PKPK, FREQ].)
    const setMeasurements = vi.spyOn(api, "setMeasurements").mockResolvedValue({ measurements: [] });
    await userEvent.click(await screen.findByLabelText("FREQ C1"));
    await waitFor(() => expect(setMeasurements).toHaveBeenLastCalledWith("abc", []));
  });
});
