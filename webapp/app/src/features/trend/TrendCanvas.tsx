import { useEffect, useRef, useState } from "react";
import { api } from "../../api/client";
import { getTrend, seedTrend, subscribeTrend } from "./trend";
import { useSession } from "../../store/session";

const TRACE = ["#FFDC32", "#40E0D0", "#FF69B4", "#32FF64", "#FFA657", "#B18CFF", "#FF7B72", "#FFFFFF"];
const DIVS_X = 14;
const DIVS_Y = 10;
const PAD = 8;

// Per-series auto-fit (units differ wildly across measurement types): min -> bottom
// margin, max -> top margin, 5% margins. Null samples are gaps, not zeros.
export function trendSeriesPixels(rows: (number | null)[][], columnIndex: number, gw: number, gh: number, pad: number): { x: number; y: number }[] {
  if (rows.length === 0) return [];
  const t0 = rows[0][0] as number;
  const t1 = rows[rows.length - 1][0] as number;
  const span = t1 - t0 || 1;
  const values = rows.map((row) => row[columnIndex + 1]).filter((v): v is number => v != null);
  if (values.length === 0) return [];
  const min = Math.min(...values);
  const max = Math.max(...values);
  const vspan = max - min || 1;
  const pixels: { x: number; y: number }[] = [];
  rows.forEach((row) => {
    const v = row[columnIndex + 1];
    if (v == null) return;
    pixels.push({
      x: pad + (((row[0] as number) - t0) / span) * gw,
      y: pad + gh - gh * 0.05 - ((v - min) / vspan) * gh * 0.9,
    });
  });
  return pixels;
}

export function seriesStats(rows: (number | null)[][], columnIndex: number): { latest: number | null; min: number | null; max: number | null } {
  const values = rows.map((row) => row[columnIndex + 1]).filter((v): v is number => v != null);
  if (values.length === 0) return { latest: null, min: null, max: null };
  return { latest: values[values.length - 1], min: Math.min(...values), max: Math.max(...values) };
}

export function formatElapsed(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  const hours = Math.floor(s / 3600);
  const minutes = Math.floor((s % 3600) / 60);
  const secs = s % 60;
  if (hours > 0) return `${hours}h ${String(minutes).padStart(2, "0")}m ${String(secs).padStart(2, "0")}s`;
  if (minutes > 0) return `${minutes}m ${String(secs).padStart(2, "0")}s`;
  return `${secs}s`;
}

const BOX = { position: "relative", flex: 1, minHeight: 320, background: "#0d1117", border: "1px solid var(--scope-border-2)", borderRadius: "var(--lc-radius)", display: "flex", flexDirection: "column" } as const;

const fmt = (v: number | null) => (v == null ? "—" : Math.abs(v) >= 1000 || (v !== 0 && Math.abs(v) < 0.01) ? v.toExponential(2) : v.toFixed(3));

export function TrendCanvas() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const session = useSession((s) => s.session);
  const startedAt = useSession((s) => s.logStatus?.started_at);
  const [trend, setTrend] = useState(getTrend());

  useEffect(() => subscribeTrend(() => setTrend(getTrend())), []);

  // Backfill from the server on mount and whenever a new recording starts —
  // the live appends only cover samples that arrived while this tab was open.
  useEffect(() => {
    if (!session) return;
    let stale = false;
    api
      .getLogData(session.id)
      .then((data) => {
        if (!stale) seedTrend(data);
      })
      .catch(() => {});
    return () => {
      stale = true;
    };
  }, [session?.id, startedAt]);

  useEffect(() => {
    const canvas = canvasRef.current;
    const wrap = wrapRef.current;
    if (!canvas || !wrap || trend.rows.length === 0) return;

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

    trend.columns.forEach((_, index) => {
      const pixels = trendSeriesPixels(trend.rows, index, gw, gh, PAD);
      if (pixels.length === 0) return;
      ctx.strokeStyle = TRACE[index % TRACE.length];
      ctx.lineWidth = 1.5;
      ctx.lineJoin = "round";
      ctx.beginPath();
      pixels.forEach(({ x, y }, i) => {
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.stroke();
    });

    const first = trend.rows[0][0] as number;
    const last = trend.rows[trend.rows.length - 1][0] as number;
    ctx.fillStyle = "#8b949e";
    ctx.font = "11px 'Segoe UI', sans-serif";
    ctx.textAlign = "right";
    ctx.fillText(`${trend.rows.length} samples · ${formatElapsed(last - first)}`, PAD + gw, PAD + 12);
  }, [trend]);

  if (trend.rows.length === 0) {
    return (
      <div style={{ ...BOX, alignItems: "center", justifyContent: "center", color: "#8b949e", fontSize: "var(--text-sm)" }}>
        <span>No recording yet — start one in the Log tab.</span>
      </div>
    );
  }

  return (
    <div style={BOX}>
      <div ref={wrapRef} style={{ position: "relative", flex: 1, minHeight: 0 }}>
        <canvas ref={canvasRef} />
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-2) var(--space-3)", padding: "6px 10px", borderTop: "1px solid var(--scope-border-2)", fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)", color: "var(--lc-text)" }}>
        {trend.columns.map((column, index) => {
          const stats = seriesStats(trend.rows, index);
          return (
            <span key={`${column.channel}-${column.mtype}`} style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
              <span aria-hidden style={{ width: 10, height: 10, borderRadius: 2, background: TRACE[index % TRACE.length] }} />
              {`C${column.channel} ${column.mtype}`}
              <span style={{ color: "var(--lc-muted)" }}>{`${fmt(stats.latest)} (min ${fmt(stats.min)} / max ${fmt(stats.max)})`}</span>
            </span>
          );
        })}
      </div>
    </div>
  );
}
