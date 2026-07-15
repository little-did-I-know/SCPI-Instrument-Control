import { useEffect, useRef } from "react";
import { getFrame, subscribeFrames } from "./frames";
import type { ChannelState } from "../../api/types";
import { useSession } from "../../store/session";

const TRACE = ["#FFDC32", "#40E0D0", "#FF69B4", "#32FF64"];
// Concrete hex (canvas 2D can't read CSS vars). Chosen far in hue from all four
// channel traces (gold/cyan/hotpink/green) so math traces stay distinguishable;
// they're also dashed below to read as "computed".
const MATH_TRACES: Record<string, string> = { M1: "#FFFFFF", M2: "#B18CFF" }; // white + light violet, distinct from channel traces
const DIVS_X = 14;
const DIVS_Y = 10;
const PAD = 8;

// Stable reference: zustand v5 hands the selector straight to useSyncExternalStore
// with no memoization, so a fresh `{}` per snapshot would loop forever while scope is null.
const NO_CHANNELS: Record<string, ChannelState> = {};

// Pure trace-point mapping for math channels (no voltage_scale): auto-fit each
// trace to its own min/max so it's visible at any amplitude. Extracted so the
// risky min/max/NaN math is unit-testable without a canvas 2D context.
export function mathTracePixels(points: number[], gw: number, gh: number, pad: number): { x: number; y: number }[] {
  if (points.length === 0) return [];
  const min = Math.min(...points);
  const max = Math.max(...points);
  const mid = (min + max) / 2;
  const halfSpan = (max - min) / 2 || 1; // flat trace → draw the mid-line, no divide-by-zero
  return points.map((v, i) => ({
    x: pad + (gw * i) / Math.max(1, points.length - 1),
    y: pad + gh / 2 - ((v - mid) / halfSpan) * ((gh / 2) * 0.9),
  }));
}

export function WaveformCanvas() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const channels = useSession((s) => s.scope?.channels ?? NO_CHANNELS);
  const enabled = Object.entries(channels)
    .filter(([, channel]) => channel.enabled)
    .map(([key]) => Number(key));
  const enabledKey = enabled.join(",");

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

      let drew = false;
      ctx.save();
      ctx.beginPath();
      ctx.rect(PAD, PAD, gw, gh);
      ctx.clip(); // keep out-of-range traces inside the graticule
      enabled.forEach((channel) => {
        const frame = getFrame(channel);
        if (!frame || frame.points.length === 0) return;
        const scale = channels[String(channel)]?.voltage_scale ?? 1;
        const fullScale = scale * DIVS_Y; // volts across the full canvas height
        ctx.strokeStyle = TRACE[(channel - 1) % TRACE.length];
        ctx.lineWidth = 2;
        ctx.lineJoin = "round";
        ctx.beginPath();
        frame.points.forEach((volts, index) => {
          const x = PAD + (gw * index) / Math.max(1, frame.points.length - 1);
          const y = PAD + gh / 2 - (volts / fullScale) * gh;
          if (index === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        });
        ctx.stroke();
        drew = true;
      });

      ["M1", "M2"].forEach((label) => {
        const frame = getFrame(label);
        if (!frame || frame.points.length === 0) return;
        const pixels = mathTracePixels(frame.points, gw, gh, PAD);
        ctx.save();
        ctx.setLineDash([5, 3]); // dashed → unmistakably a computed math trace
        ctx.strokeStyle = MATH_TRACES[label];
        ctx.lineWidth = 2;
        ctx.lineJoin = "round";
        ctx.beginPath();
        pixels.forEach(({ x, y }, index) => {
          if (index === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        });
        ctx.stroke();
        ctx.restore();
        drew = true;
      });
      ctx.restore();

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
  }, [enabledKey, channels]);

  return (
    <div ref={wrapRef} style={{ position: "relative", flex: 1, minHeight: 320, background: "#0d1117", border: "1px solid var(--scope-border-2)", borderRadius: "var(--lc-radius)" }}>
      <canvas ref={canvasRef} />
    </div>
  );
}
