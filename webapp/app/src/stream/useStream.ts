import { useEffect } from "react";
import { getToken } from "../api/token";
import type { StreamMessage } from "../api/types";
import { appendTrend, clearTrend, seedTrend } from "../features/trend/trend";
import { clearFrames, setFrame } from "../features/waveform/frames";
import { clearSpectrum, setSpectrum } from "../features/waveform/spectrum";
import { useSession } from "../store/session";

const CLOSE_SESSION_ENDED = 4410;

export function useStream(sessionId: string | null): void {
  useEffect(() => {
    if (!sessionId) return;

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const token = getToken();
    const subprotocols = token ? [`scpi-token.${token}`, "scpi"] : ["scpi"];
    const socket = new WebSocket(`${protocol}//${window.location.host}/api/sessions/${sessionId}/stream`, subprotocols);
    let ended = false;

    socket.onmessage = (event: MessageEvent) => {
      const message = JSON.parse(event.data as string) as StreamMessage;
      const store = useSession.getState();
      if (message.type === "state") store.applyState(message.state);
      else if (message.type === "waveform") setFrame(message.channel, { t0: message.t0, dt: message.dt, points: message.points });
      else if (message.type === "measurements") {
        store.applyMeasurements(message.values);
        if (message.timestamp != null && store.logStatus?.state === "recording") appendTrend(message.timestamp, message.values);
      }
      else if (message.type === "measurements_config") store.applyMeasurementConfig(message.items);
      else if (message.type === "log_status") {
        store.applyLogStatus({ state: message.state, started_at: message.started_at, row_count: message.row_count, columns: message.columns });
        if (message.state === "recording" && message.row_count === 0) seedTrend({ columns: message.columns, rows: [] }); // fresh recording: reset the client buffer
      }
      else if (message.type === "spectrum") setSpectrum(message.points.length ? message : null);
      else if (message.type === "reference") {
        setFrame("REF", { t0: message.t0, dt: message.dt, points: message.points });
        store.applyReference(message.name ? { name: message.name, channel: message.channel } : null);
      } else if (message.type === "reference_stats") store.applyReferenceStats({ correlation: message.correlation, max_deviation: message.max_deviation });
      else if (message.type === "error") store.setError(message.detail);
      else if (message.type === "closed") {
        ended = true;
        clearFrames();
        clearSpectrum();
        clearTrend();
        store.clearSession();
      }
    };

    socket.onclose = (event: CloseEvent) => {
      if (ended || event.code === CLOSE_SESSION_ENDED) {
        clearFrames();
        clearSpectrum();
        clearTrend();
        useSession.getState().clearSession();
        return;
      }
      useSession.getState().setError("stream disconnected");
    };

    return () => {
      // close() is async in browsers: detach the handlers so this socket's late
      // close event can never clear/error a session a newer socket already owns.
      socket.onmessage = null;
      socket.onclose = null;
      socket.onerror = null;
      socket.close();
      clearFrames();
      clearSpectrum();
      clearTrend();
    };
  }, [sessionId]);
}
