import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useStream } from "./useStream";
import { useSession } from "../store/session";
import { getFrame, clearFrames } from "../features/waveform/frames";
import { getSpectrum, clearSpectrum } from "../features/waveform/spectrum";
import { clearTrend, getTrend, seedTrend } from "../features/trend/trend";
import { setToken, clearToken } from "../api/token";

class FakeWebSocket {
  static last: FakeWebSocket | null = null;
  url: string;
  protocols: string[] | undefined;
  onmessage: ((event: { data: string }) => void) | null = null;
  onclose: ((event: { code: number }) => void) | null = null;
  onerror: (() => void) | null = null;
  closed = false;

  constructor(url: string, protocols?: string | string[]) {
    this.url = url;
    this.protocols = protocols === undefined ? undefined : ([] as string[]).concat(protocols);
    FakeWebSocket.last = this;
  }

  send() {}
  close(code = 1000) {
    this.closed = true;
    queueMicrotask(() => this.onclose?.({ code } as CloseEvent));
  }

  emit(message: unknown) {
    this.onmessage?.({ data: JSON.stringify(message) });
  }

  emitClose(code: number) {
    queueMicrotask(() => this.onclose?.({ code } as CloseEvent));
  }
}

const SESSION = { id: "abc", label: "x", mock: true, address: null, state: "connected", idn: "", model: "", dialect: "legacy", num_channels: 4, viewers: 0, owner: "", kind: "scope" as const };

beforeEach(() => {
  vi.stubGlobal("WebSocket", FakeWebSocket as unknown as typeof WebSocket);
  useSession.getState().clearSession();
  clearFrames();
  clearSpectrum();
  clearTrend();
  clearToken();
});

const STATE = { run_state: "STOP", timebase: 0.001, channels: { "1": { enabled: true, voltage_scale: 0.5, voltage_offset: 0, coupling: "DC", probe_ratio: 10 } }, trigger: { mode: "AUTO", source: "C1", level: 0, slope: "POS", coupling: "DC" } };

describe("useStream", () => {
  it("opens a socket for the session and applies state messages to the store", async () => {
    renderHook(() => useStream("abc"));
    expect(FakeWebSocket.last?.url).toContain("/api/sessions/abc/stream");

    FakeWebSocket.last!.emit({ type: "state", state: STATE });
    await waitFor(() => expect(useSession.getState().scope?.timebase).toBe(0.001));
  });

  it("routes a psu state message to the psu store slot, not the scope slot", async () => {
    renderHook(() => useStream("abc"));
    FakeWebSocket.last!.emit({
      type: "state",
      kind: "psu",
      outputs: [{ output: 1, voltage: 3.3, current: 0.5, enabled: false, measured_voltage: 3.31, measured_current: 0.12, measured_power: 0.4 }],
    });
    await waitFor(() => expect(useSession.getState().psu?.outputs[0].measured_voltage).toBe(3.31));
    expect(useSession.getState().scope).toBeNull();
  });

  it("routes an awg state message to the awg store slot, not the scope or psu slot", async () => {
    renderHook(() => useStream("abc"));
    FakeWebSocket.last!.emit({
      type: "state",
      kind: "awg",
      channels: [{ channel: 1, function: "SINE", frequency: 1000, amplitude: 2, offset: 0, phase: 0, enabled: true, duty_cycle: null, symmetry: null }],
    });
    await waitFor(() => expect(useSession.getState().awg?.channels[0].frequency).toBe(1000));
    expect(useSession.getState().scope).toBeNull();
    expect(useSession.getState().psu).toBeNull();
  });

  it("routes waveform frames to the frame buffer, not the store", async () => {
    renderHook(() => useStream("abc"));
    FakeWebSocket.last!.emit({ type: "waveform", channel: 1, t0: 0, dt: 1e-6, points: [0, 0.5, 1] });

    await waitFor(() => expect(getFrame(1)?.points).toEqual([0, 0.5, 1]));
    expect(useSession.getState().scope).toBeNull();
  });

  it("applies measurement messages", async () => {
    renderHook(() => useStream("abc"));
    FakeWebSocket.last!.emit({ type: "measurements", values: [{ channel: 1, mtype: "PKPK", value: 2 }] });
    await waitFor(() => expect(useSession.getState().measurements[0].value).toBe(2));
  });

  it("applies a measurements_config message to the store", async () => {
    renderHook(() => useStream("abc"));
    FakeWebSocket.last!.emit({ type: "measurements_config", items: [{ channel: 1, mtype: "PKPK" }] });
    await waitFor(() => expect(useSession.getState().measurementConfig).toEqual([{ channel: 1, mtype: "PKPK" }]));
  });

  it("routes a math (M1) waveform frame to the frame buffer", async () => {
    renderHook(() => useStream("abc"));
    FakeWebSocket.last!.emit({ type: "waveform", channel: "M1", t0: 0, dt: 1e-6, points: [0, 1] });
    await waitFor(() => expect(getFrame("M1")?.points).toEqual([0, 1]));
  });

  it("treats a closed message as a clean session end", async () => {
    useSession.getState().setSession({ id: "abc", label: "x", mock: true, address: null, state: "connected", idn: "", model: "", dialect: "legacy", num_channels: 4, viewers: 0, owner: "", kind: "scope" });
    renderHook(() => useStream("abc"));
    FakeWebSocket.last!.emit({ type: "closed" });
    await waitFor(() => expect(useSession.getState().session).toBeNull());
    expect(useSession.getState().status).toBe("disconnected");
  });

  it("surfaces an error message as an error status", async () => {
    renderHook(() => useStream("abc"));
    FakeWebSocket.last!.emit({ type: "error", detail: "connection lost" });
    await waitFor(() => expect(useSession.getState().status).toBe("error"));
    expect(useSession.getState().error).toBe("connection lost");
  });

  it("closes the socket on unmount and opens none without a session", () => {
    const { unmount } = renderHook(() => useStream("abc"));
    const socket = FakeWebSocket.last!;
    unmount();
    expect(socket.closed).toBe(true);

    FakeWebSocket.last = null;
    renderHook(() => useStream(null));
    expect(FakeWebSocket.last).toBeNull();
  });

  it("treats a 4410 close from the live socket as a clean session end", async () => {
    useSession.getState().setSession(SESSION);
    renderHook(() => useStream("abc"));

    FakeWebSocket.last!.emitClose(4410);
    await waitFor(() => expect(useSession.getState().session).toBeNull());
    expect(useSession.getState().status).toBe("disconnected");
  });

  it("surfaces an unexpected close from the live socket as an error", async () => {
    useSession.getState().setSession(SESSION);
    renderHook(() => useStream("abc"));

    FakeWebSocket.last!.emitClose(1006);
    await waitFor(() => expect(useSession.getState().status).toBe("error"));
    expect(useSession.getState().error).toBe("stream disconnected");
  });

  it("ignores a late close from an already torn-down socket", async () => {
    const first = renderHook(() => useStream("abc"));
    const staleSocket = FakeWebSocket.last!;
    first.unmount();

    // A second, live stream takes over (StrictMode remount / session-id change).
    renderHook(() => useStream("abc"));
    const liveSocket = FakeWebSocket.last!;
    expect(liveSocket).not.toBe(staleSocket);
    useSession.getState().setSession(SESSION);

    // The dead socket's close events land late — they must not touch the store.
    staleSocket.emitClose(1006);
    staleSocket.emitClose(4410);
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(useSession.getState().session).toEqual(SESSION);
    expect(useSession.getState().status).toBe("connected");
    expect(useSession.getState().error).toBeNull();
  });

  it("routes a spectrum frame to the spectrum buffer", async () => {
    renderHook(() => useStream("abc"));
    FakeWebSocket.last!.emit({ type: "spectrum", channel: 1, f0: 0, df: 10, points: [1, 2], db: true, window: "hanning", peaks: [], thd: null });
    await waitFor(() => expect(getSpectrum()?.points).toEqual([1, 2]));
  });

  it("clears the spectrum buffer on an empty spectrum frame", async () => {
    renderHook(() => useStream("abc"));
    FakeWebSocket.last!.emit({ type: "spectrum", channel: 1, f0: 0, df: 10, points: [1], db: true, window: "hanning", peaks: [], thd: null });
    await waitFor(() => expect(getSpectrum()).not.toBeNull());
    FakeWebSocket.last!.emit({ type: "spectrum", channel: 1, f0: 0, df: 1, points: [], db: true, window: "hanning", peaks: [], thd: null });
    await waitFor(() => expect(getSpectrum()).toBeNull());
  });

  it("applies a reference broadcast to the frame buffer and store", async () => {
    renderHook(() => useStream("abc"));
    FakeWebSocket.last!.emit({ type: "reference", name: "golden", channel: 1, t0: 0, dt: 1, points: [1, 2] });
    await waitFor(() => expect(getFrame("REF")?.points).toEqual([1, 2]));
    expect(useSession.getState().activeReference).toEqual({ name: "golden", channel: 1 });
  });

  it("clears the reference on a null-name broadcast", async () => {
    renderHook(() => useStream("abc"));
    FakeWebSocket.last!.emit({ type: "reference", name: "golden", channel: 1, t0: 0, dt: 1, points: [1, 2] });
    await waitFor(() => expect(useSession.getState().activeReference).not.toBeNull());
    FakeWebSocket.last!.emit({ type: "reference", name: null, channel: null, t0: 0, dt: 1, points: [] });
    await waitFor(() => expect(useSession.getState().activeReference).toBeNull());
    expect(getFrame("REF")?.points).toEqual([]);
  });

  it("applies reference stats to the store", async () => {
    renderHook(() => useStream("abc"));
    FakeWebSocket.last!.emit({ type: "reference_stats", correlation: 0.9, max_deviation: 0.1 });
    await waitFor(() => expect(useSession.getState().referenceStats).toEqual({ correlation: 0.9, max_deviation: 0.1 }));
  });

  it("applies a log_status message to the store and seeds a fresh trend buffer", async () => {
    renderHook(() => useStream("abc"));
    seedTrend({ columns: [{ channel: 3, mtype: "MAX" }], rows: [[1, 9]] }); // stale previous recording
    FakeWebSocket.last!.emit({ type: "log_status", state: "recording", started_at: 100, row_count: 0, columns: [{ channel: 1, mtype: "PKPK" }] });
    await waitFor(() => expect(useSession.getState().logStatus?.state).toBe("recording"));
    expect(getTrend().columns).toEqual([{ channel: 1, mtype: "PKPK" }]);
    expect(getTrend().rows).toEqual([]); // fresh start replaced the stale buffer
  });

  it("appends timestamped measurements to the trend buffer while recording", async () => {
    renderHook(() => useStream("abc"));
    FakeWebSocket.last!.emit({ type: "log_status", state: "recording", started_at: 100, row_count: 0, columns: [{ channel: 1, mtype: "PKPK" }] });
    FakeWebSocket.last!.emit({ type: "measurements", values: [{ channel: 1, mtype: "PKPK", value: 2 }], timestamp: 101 });
    await waitFor(() => expect(getTrend().rows).toEqual([[101, 2]]));
    expect(useSession.getState().measurements[0].value).toBe(2); // display path unaffected
  });

  it("does not append measurements while idle", async () => {
    renderHook(() => useStream("abc"));
    seedTrend({ columns: [{ channel: 1, mtype: "PKPK" }], rows: [] });
    FakeWebSocket.last!.emit({ type: "measurements", values: [{ channel: 1, mtype: "PKPK", value: 2 }], timestamp: 101 });
    await waitFor(() => expect(useSession.getState().measurements.length).toBe(1));
    expect(getTrend().rows).toEqual([]);
  });

  it("offers the token subprotocol", () => {
    setToken("scpi_wstoken");
    renderHook(() => useStream("abc"));
    expect(FakeWebSocket.last?.protocols).toEqual(["scpi-token.scpi_wstoken", "scpi"]);
  });

  it("offers no token subprotocol when unauthenticated", () => {
    clearToken();
    renderHook(() => useStream("abc"));
    expect(FakeWebSocket.last?.protocols).toEqual(["scpi"]);
  });
});
