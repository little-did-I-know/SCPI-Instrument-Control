import { useCallback, useEffect, useRef } from "react";
import { getFrame, subscribeFrames } from "./frames";
import type { ChannelState } from "../../api/types";
import { useSession } from "../../store/session";
import { envelope, traceRange, type Envelope } from "./envelope";
import { DIVS_X, formatSeconds, fullView, resolve, type TimeRecord, type View } from "./view";
import { useCanvasGestures } from "./useCanvasGestures";

const TRACE = ["#FFDC32", "#40E0D0", "#FF69B4", "#32FF64"];
// Computed traces (math + filters): concrete hex (canvas 2D can't read CSS vars),
// chosen far in hue from the four channel colors. Dashes mark them as computed;
// filters get a tighter dash than math so the two families stay tellable apart.
const COMPUTED_TRACES: Record<string, { color: string; dash: number[] }> = {
  M1: { color: "#FFFFFF", dash: [5, 3] },
  M2: { color: "#B18CFF", dash: [5, 3] },
  F1: { color: "#FFA657", dash: [2, 2] },
  F2: { color: "#FF7B72", dash: [2, 2] },
};
const REF_TRACE = { color: "#8B949E", dash: [8, 4] };
const DIVS_Y = 10;
const PAD = 8;
const BAND_ALPHA = 0.35;

// Stable reference: zustand v5 hands the selector straight to useSyncExternalStore
// with no memoization, so a fresh `{}` per snapshot would loop forever while scope is null.
const NO_CHANNELS: Record<string, ChannelState> = {};

/** The record the view is measured against: the first enabled channel with data, else any live trace. */
export function currentRecord(enabled: number[]): TimeRecord | null {
  const keys: (number | string)[] = [...enabled, "M1", "M2", "F1", "F2", "REF"];
  for (const key of keys) {
    const f = getFrame(key);
    if (f && f.points.length > 0) return { t0: f.t0, dt: f.dt, n: f.points.length };
  }
  return null;
}

export type YMap = (v: number) => number;

/** Volts -> canvas y for a channel at `voltsPerDiv`; auto-fit when no scale is known (math traces). */
function yMapper(points: ArrayLike<number>, voltsPerDiv: number | undefined, gh: number): YMap {
  if (voltsPerDiv) {
    const fullScale = voltsPerDiv * DIVS_Y;
    return (v) => PAD + gh / 2 - (v / fullScale) * gh;
  }
  const r = traceRange(points);
  const mid = r ? (r.min + r.max) / 2 : 0;
  const halfSpan = r && r.max > r.min ? (r.max - r.min) / 2 : 1; // flat trace -> mid-line, no divide-by-zero
  return (v) => PAD + gh / 2 - ((v - mid) / halfSpan) * ((gh / 2) * 0.9);
}

export function strokeEnvelope(ctx: CanvasRenderingContext2D, env: Envelope, y: YMap, color: string, dash: number[], width: number): void {
  ctx.save();
  ctx.setLineDash(dash);
  ctx.strokeStyle = color;
  ctx.lineWidth = width;
  ctx.lineJoin = "round";
  if (env.mode === "poly") {
    ctx.beginPath();
    let pen = false;
    for (let k = 0; k < env.xs.length; k++) {
      if (env.ys[k] !== env.ys[k]) {
        pen = false;
        continue;
      }
      const px = PAD + env.xs[k];
      const py = y(env.ys[k]);
      if (!pen) ctx.moveTo(px, py);
      else ctx.lineTo(px, py);
      pen = true;
    }
    ctx.stroke();
  } else {
    // Filled min/max band (translucent) so a glitch shows as a spike, plus a
    // solid stroke along the column mean so the trace still reads as a line.
    ctx.globalAlpha = BAND_ALPHA;
    ctx.fillStyle = color;
    let open = false;
    let start = 0;
    for (let c = 0; c <= env.mins.length; c++) {
      const gap = c === env.mins.length || env.mins[c] !== env.mins[c];
      if (!gap && !open) {
        open = true;
        start = c;
        ctx.beginPath();
        ctx.moveTo(PAD + c, y(env.maxs[c]));
      } else if (!gap) ctx.lineTo(PAD + c, y(env.maxs[c]));
      if (gap && open) {
        for (let k = c - 1; k >= start; k--) ctx.lineTo(PAD + k, y(env.mins[k]));
        ctx.closePath();
        ctx.fill();
        open = false;
      }
    }
    ctx.globalAlpha = 1;
    ctx.beginPath();
    let pen = false;
    for (let c = 0; c < env.means.length; c++) {
      const m = env.means[c];
      if (m !== m) {
        pen = false;
        continue;
      }
      if (!pen) ctx.moveTo(PAD + c, y(m));
      else ctx.lineTo(PAD + c, y(m));
      pen = true;
    }
    ctx.stroke();
  }
  ctx.restore();
}

export function WaveformCanvas() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const channels = useSession((s) => s.scope?.channels ?? NO_CHANNELS);
  const activeReference = useSession((s) => s.activeReference);
  const view = useSession((s) => s.view);
  const setView = useSession((s) => s.setView);
  const enabled = Object.entries(channels)
    .filter(([, channel]) => channel.enabled)
    .map(([key]) => Number(key));
  const enabledKey = enabled.join(",");
  const enabledRef = useRef(enabled);
  enabledRef.current = enabled;

  const getGeometry = useCallback(() => {
    const wrap = wrapRef.current;
    return { rec: currentRecord(enabledRef.current), plotLeft: PAD, plotWidth: Math.max(1, (wrap?.clientWidth ?? 0) - PAD * 2) };
  }, []);
  useCanvasGestures(canvasRef, getGeometry);

  useEffect(() => {
    const canvas = canvasRef.current;
    const wrap = wrapRef.current;
    if (!canvas || !wrap) return;

    let raf = 0;
    let dirty = true;
    const unsubscribe = subscribeFrames(() => {
      dirty = true;
    });

    const draw = () => {
      raf = requestAnimationFrame(draw);
      if (!dirty) return;
      dirty = false;

      const dpr = window.devicePixelRatio || 1;
      const w = wrap.clientWidth;
      const h = wrap.clientHeight;
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      canvas.style.width = `${w}px`;
      canvas.style.height = `${h}px`;

      const ctx = canvas.getContext("2d");
      if (!ctx) return;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.fillStyle = "#0d1117";
      ctx.fillRect(0, 0, w, h);

      const gw = w - PAD * 2;
      const gh = h - PAD * 2;

      ctx.save();
      ctx.setLineDash([1, 3]);
      ctx.strokeStyle = "#30363d";
      ctx.lineWidth = 1;
      for (let i = 1; i < DIVS_X; i += 1) {
        const x = PAD + (gw * i) / DIVS_X;
        ctx.beginPath();
        ctx.moveTo(x, PAD);
        ctx.lineTo(x, PAD + gh);
        ctx.stroke();
      }
      for (let i = 1; i < DIVS_Y; i += 1) {
        const y = PAD + (gh * i) / DIVS_Y;
        ctx.beginPath();
        ctx.moveTo(PAD, y);
        ctx.lineTo(PAD + gw, y);
        ctx.stroke();
      }
      ctx.restore();

      ctx.strokeStyle = "#3d444d";
      ctx.beginPath();
      ctx.moveTo(PAD + gw / 2, PAD);
      ctx.lineTo(PAD + gw / 2, PAD + gh);
      ctx.moveTo(PAD, PAD + gh / 2);
      ctx.lineTo(PAD + gw, PAD + gh / 2);
      ctx.stroke();

      const rec = currentRecord(enabled);
      let drew = false;
      if (rec) {
        const win: View = resolve(view, rec);
        const tStart = win.tCenter - win.tSpan / 2;
        ctx.save();
        ctx.beginPath();
        ctx.rect(PAD, PAD, gw, gh);
        ctx.clip(); // keep out-of-range traces inside the graticule

        const ref = getFrame("REF");
        if (ref && ref.points.length > 0) {
          const scale = activeReference?.channel != null ? channels[String(activeReference.channel)]?.voltage_scale : undefined;
          const env = envelope(ref.points, ref.t0, ref.dt, tStart, win.tSpan, gw);
          if (env) {
            strokeEnvelope(ctx, env, yMapper(ref.points, scale, gh), REF_TRACE.color, REF_TRACE.dash, 1.5);
            drew = true;
          }
        }

        enabled.forEach((channel) => {
          const frame = getFrame(channel);
          if (!frame || frame.points.length === 0) return;
          const env = envelope(frame.points, frame.t0, frame.dt, tStart, win.tSpan, gw);
          if (!env) return;
          strokeEnvelope(ctx, env, yMapper(frame.points, channels[String(channel)]?.voltage_scale ?? 1, gh), TRACE[(channel - 1) % TRACE.length], [], 2);
          drew = true;
        });

        Object.keys(COMPUTED_TRACES).forEach((label) => {
          const frame = getFrame(label);
          if (!frame || frame.points.length === 0) return;
          const env = envelope(frame.points, frame.t0, frame.dt, tStart, win.tSpan, gw);
          if (!env) return;
          strokeEnvelope(ctx, env, yMapper(frame.points, undefined, gh), COMPUTED_TRACES[label].color, COMPUTED_TRACES[label].dash, 2);
          drew = true;
        });
        ctx.restore();

        // Readout: effective time/div, plus the centre offset while zoomed.
        const offset = win.tCenter - fullView(rec).tCenter;
        ctx.fillStyle = "#8b949e";
        ctx.font = "12px 'Segoe UI', sans-serif";
        ctx.textAlign = "right";
        ctx.fillText(view ? `${formatSeconds(win.tSpan / DIVS_X)}/div  ·  offset ${formatSeconds(offset)}` : `${formatSeconds(win.tSpan / DIVS_X)}/div`, w - PAD - 4, PAD + 14);
      }

      if (!drew) {
        ctx.fillStyle = "#8b949e";
        ctx.font = "13px 'Segoe UI', sans-serif";
        ctx.textAlign = "center";
        ctx.fillText("No data — enable a channel and press Run", w / 2, h / 2);
      }
    };

    raf = requestAnimationFrame(draw);
    return () => {
      cancelAnimationFrame(raf);
      unsubscribe();
    };
  }, [enabledKey, channels, activeReference, view]);

  return (
    <div ref={wrapRef} style={{ position: "relative", flex: 1, minHeight: 320, background: "#0d1117", border: "1px solid var(--scope-border-2)", borderRadius: "var(--lc-radius)" }}>
      <canvas ref={canvasRef} style={{ touchAction: "none", userSelect: "none", WebkitUserSelect: "none", cursor: view ? "grab" : "default" }} />
      {view && (
        <button
          type="button"
          onClick={() => setView(null)}
          title="Fit the whole record (double-click the trace does the same)"
          style={{ position: "absolute", top: 6, left: 6, padding: "2px 8px", fontSize: 12, borderRadius: "var(--lc-radius-sm)", border: "1px solid var(--lc-border-strong)", background: "var(--lc-control)", color: "var(--lc-text)", cursor: "pointer" }}
        >
          ⟲ fit
        </button>
      )}
    </div>
  );
}
