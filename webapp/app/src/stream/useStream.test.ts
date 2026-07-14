import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useStream } from "./useStream";
import { useSession } from "../store/session";
import { getFrame, clearFrames } from "../features/waveform/frames";

class FakeWebSocket {
  static last: FakeWebSocket | null = null;
  url: string;
  onmessage: ((event: { data: string }) => void) | null = null;
  onclose: ((event: { code: number }) => void) | null = null;
  onerror: (() => void) | null = null;
  closed = false;

  constructor(url: string) {
    this.url = url;
    FakeWebSocket.last = this;
  }

  send() {}
  close() {
    this.closed = true;
  }

  emit(message: unknown) {
    this.onmessage?.({ data: JSON.stringify(message) });
  }
}

beforeEach(() => {
  vi.stubGlobal("WebSocket", FakeWebSocket as unknown as typeof WebSocket);
  useSession.getState().clearSession();
  clearFrames();
});

const STATE = { run_state: "STOP", timebase: 0.001, channels: { "1": { enabled: true, voltage_scale: 0.5, voltage_offset: 0, coupling: "DC", probe_ratio: 10 } }, trigger: { mode: "AUTO", source: "C1", level: 0, slope: "POS", coupling: "DC" } };

describe("useStream", () => {
  it("opens a socket for the session and applies state messages to the store", async () => {
    renderHook(() => useStream("abc"));
    expect(FakeWebSocket.last?.url).toContain("/api/sessions/abc/stream");

    FakeWebSocket.last!.emit({ type: "state", state: STATE });
    await waitFor(() => expect(useSession.getState().scope?.timebase).toBe(0.001));
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

  it("treats a closed message as a clean session end", async () => {
    useSession.getState().setSession({ id: "abc", label: "x", mock: true, address: null, state: "connected", idn: "", model: "", dialect: "legacy", num_channels: 4 });
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
});
