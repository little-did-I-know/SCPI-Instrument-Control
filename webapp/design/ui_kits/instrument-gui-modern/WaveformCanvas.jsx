// WaveformCanvas — the dark scope display: 14×10 division grid + animated
// channel traces. Data-visualization canvas (not iconography). Colours come
// from the design-system trace tokens.
function WaveformCanvas({ channels, running, showGrid }) {
  const canvasRef = React.useRef(null);
  const wrapRef = React.useRef(null);
  const phaseRef = React.useRef(0);
  const rafRef = React.useRef(null);

  const TRACE = {
    1: "#FFDC32", 2: "#40E0D0", 3: "#FF69B4", 4: "#32FF64",
  };

  React.useEffect(() => {
    const canvas = canvasRef.current;
    const wrap = wrapRef.current;
    if (!canvas || !wrap) return;
    const ctx = canvas.getContext("2d");

    const draw = () => {
      const dpr = window.devicePixelRatio || 1;
      const w = wrap.clientWidth, h = wrap.clientHeight;
      if (canvas.width !== w * dpr || canvas.height !== h * dpr) {
        canvas.width = w * dpr; canvas.height = h * dpr;
        canvas.style.width = w + "px"; canvas.style.height = h + "px";
      }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, w, h);

      // background
      ctx.fillStyle = "#0d1117";
      ctx.fillRect(0, 0, w, h);

      const padL = 8, padR = 8, padT = 8, padB = 8;
      const gx = padL, gy = padT, gw = w - padL - padR, gh = h - padT - padB;

      // grid — 14 x 10 divisions, dotted
      if (showGrid) {
        ctx.strokeStyle = "#30363d";
        ctx.lineWidth = 1;
        ctx.setLineDash([1, 3]);
        for (let i = 0; i <= 14; i++) {
          const x = gx + (gw * i) / 14;
          ctx.beginPath(); ctx.moveTo(x, gy); ctx.lineTo(x, gy + gh); ctx.stroke();
        }
        for (let j = 0; j <= 10; j++) {
          const y = gy + (gh * j) / 10;
          ctx.beginPath(); ctx.moveTo(gx, y); ctx.lineTo(gx + gw, y); ctx.stroke();
        }
        ctx.setLineDash([]);
        // center crosshair, slightly brighter
        ctx.strokeStyle = "#3d444d";
        ctx.beginPath(); ctx.moveTo(gx + gw / 2, gy); ctx.lineTo(gx + gw / 2, gy + gh); ctx.stroke();
        ctx.beginPath(); ctx.moveTo(gx, gy + gh / 2); ctx.lineTo(gx + gw, gy + gh / 2); ctx.stroke();
      }

      // traces
      const active = channels.filter((c) => c.enabled);
      if (active.length === 0) {
        ctx.fillStyle = "#8b949e";
        ctx.font = "13px 'Segoe UI', system-ui, sans-serif";
        ctx.textAlign = "center";
        ctx.fillText("No data — enable a channel", w / 2, h / 2);
      } else {
        active.forEach((c) => {
          ctx.strokeStyle = TRACE[c.num] || "#ffffff";
          ctx.lineWidth = 2;
          ctx.lineJoin = "round";
          ctx.beginPath();
          const cyc = c.freq;      // cycles across the screen
          const amp = (gh / 2) * c.amp;
          const yMid = gy + gh / 2 - c.offset * (gh / 10);
          for (let px = 0; px <= gw; px++) {
            const t = px / gw;
            let v;
            if (c.shape === "square") {
              v = Math.sign(Math.sin(2 * Math.PI * cyc * t + phaseRef.current + c.phase)) || 1;
            } else if (c.shape === "triangle") {
              v = (2 / Math.PI) * Math.asin(Math.sin(2 * Math.PI * cyc * t + phaseRef.current + c.phase));
            } else {
              v = Math.sin(2 * Math.PI * cyc * t + phaseRef.current + c.phase);
            }
            const x = gx + px;
            const y = yMid - v * amp;
            px === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
          }
          ctx.stroke();
        });
      }
    };

    let last = performance.now();
    const loop = (now) => {
      if (running) { phaseRef.current += (now - last) / 1000 * 3; }
      last = now;
      draw();
      rafRef.current = requestAnimationFrame(loop);
    };
    rafRef.current = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(rafRef.current);
  }, [channels, running, showGrid]);

  return (
    <div ref={wrapRef} style={{ position: "relative", width: "100%", height: "100%" }}>
      <canvas ref={canvasRef} style={{ display: "block" }} />
      <div style={{
        position: "absolute", top: 8, left: 0, right: 0, textAlign: "center",
        color: "#e6edf3", fontFamily: "var(--font-ui)", fontSize: "15px", pointerEvents: "none",
      }}>Waveform Display</div>
      <div style={{
        position: "absolute", left: 10, top: "50%", transform: "rotate(-90deg) translateX(50%)",
        transformOrigin: "left center", color: "#8b949e", fontSize: "11px", fontFamily: "var(--font-ui)", pointerEvents: "none",
      }}>Voltage (V)</div>
      <div style={{
        position: "absolute", bottom: 8, left: 0, right: 0, textAlign: "center",
        color: "#8b949e", fontSize: "11px", fontFamily: "var(--font-ui)", pointerEvents: "none",
      }}>Time (s)</div>
    </div>
  );
}
window.WaveformCanvas = WaveformCanvas;
