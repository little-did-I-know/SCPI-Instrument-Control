import { useEffect, useRef, useState } from "react";
import { ApiError, api } from "../../api/client";
import type { SpectrumFrame } from "../../api/types";
import { getSpectrum, subscribeSpectrum } from "./spectrum";
import { useSession } from "../../store/session";

const TRACE = ["#FFDC32", "#40E0D0", "#FF69B4", "#32FF64"]; // same channel colors as WaveformCanvas
const DIVS_X = 14;
const DIVS_Y = 10;
const PAD = 8;
const AXIS_PAD = 18; // strip below the graticule for frequency labels

// Auto-fit the magnitude range with a 5% margin top and bottom. Extracted so
// the min/max math is unit-testable without a canvas 2D context.
export function spectrumTracePixels(points: number[], gw: number, gh: number, pad: number): { x: number; y: number }[] {
  if (points.length === 0) return [];
  const min = Math.min(...points);
  const max = Math.max(...points);
  const span = max - min || 1;
  return points.map((v, i) => ({
    x: pad + (gw * i) / Math.max(1, points.length - 1),
    y: pad + gh - gh * 0.05 - ((v - min) / span) * gh * 0.9,
  }));
}

export function formatHz(hz: number): string {
  if (!Number.isFinite(hz)) return "";
  if (hz >= 1e9) return `${(hz / 1e9).toFixed(1)} GHz`;
  if (hz >= 1e6) return `${(hz / 1e6).toFixed(1)} MHz`;
  if (hz >= 1e3) return `${(hz / 1e3).toFixed(1)} kHz`;
  return `${hz.toFixed(1)} Hz`;
}

const BOX = { position: "relative", flex: 1, minHeight: 320, background: "#0d1117", border: "1px solid var(--scope-border-2)", borderRadius: "var(--lc-radius)" } as const;

export function SpectrumCanvas() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const session = useSession((s) => s.session);
  const [frame, setSpectrumFrame] = useState<SpectrumFrame | null>(getSpectrum());
  const [error, setError] = useState<string | null>(null);

  useEffect(() => subscribeSpectrum(() => setSpectrumFrame(getSpectrum())), []);

  useEffect(() => {
    const canvas = canvasRef.current;
    const wrap = wrapRef.current;
    if (!canvas || !wrap || !frame || frame.points.length === 0) return;

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
    const gh = h - PAD * 2 - AXIS_PAD;

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

    const pixels = spectrumTracePixels(frame.points, gw, gh, PAD);
    ctx.strokeStyle = TRACE[(frame.channel - 1) % TRACE.length];
    ctx.lineWidth = 1.5;
    ctx.lineJoin = "round";
    ctx.beginPath();
    pixels.forEach(({ x, y }, index) => {
      if (index === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();

    const fmax = frame.df * Math.max(1, frame.points.length - 1);
    ctx.fillStyle = "#e6edf3";
    ctx.font = "11px 'Segoe UI', sans-serif";
    ctx.textAlign = "center";
    frame.peaks.slice(0, 3).forEach(([freq]) => {
      const x = PAD + (gw * freq) / (fmax || 1);
      ctx.fillText(`▼ ${formatHz(freq)}`, x, PAD + 12);
    });

    ctx.fillStyle = "#8b949e";
    ctx.textAlign = "left";
    ctx.fillText("0 Hz", PAD, h - 4);
    ctx.textAlign = "right";
    ctx.fillText(formatHz(fmax), PAD + gw, h - 4);
    const unit = frame.db ? "dB" : "linear";
    const thd = frame.thd == null ? "" : ` · THD ${frame.thd.toFixed(1)}%`;
    ctx.fillText(`C${frame.channel} · ${frame.window} · ${unit}${thd}`, PAD + gw, PAD + gh - 6);
  }, [frame]);

  async function enable() {
    if (!session) return;
    setError(null);
    try {
      await api.patchSpectrum(session.id, { enabled: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : String(err));
    }
  }

  if (!frame || frame.points.length === 0) {
    return (
      <div style={{ ...BOX, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: "var(--space-2)", color: "#8b949e", fontSize: "var(--text-sm)" }}>
        <span>No spectrum — the source channel must be enabled and acquiring</span>
        <button onClick={enable} style={{ padding: "6px 14px", borderRadius: "var(--lc-radius-sm)", border: "1px solid var(--lc-border-strong)", background: "var(--lc-control)", color: "var(--lc-text)", cursor: "pointer" }}>
          Enable spectrum
        </button>
        {error && <span role="alert" style={{ color: "var(--danger)" }}>{error}</span>}
      </div>
    );
  }

  return (
    <div ref={wrapRef} style={BOX}>
      <canvas ref={canvasRef} />
    </div>
  );
}
