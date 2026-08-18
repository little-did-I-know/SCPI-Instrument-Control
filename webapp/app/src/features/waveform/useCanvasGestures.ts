import { useEffect, type RefObject } from "react";
import { useSession } from "../../store/session";
import { pan, zoomAt, type TimeRecord } from "./view";

export type Geometry = { rec: TimeRecord | null; plotLeft: number; plotWidth: number };

const WHEEL_STEP = 1.25; // one notch = 25% span change

/**
 * Wheel zoom about the pointer, drag to pan, two-pointer pinch to zoom, double-click to fit.
 * Pointer events only (mouse, pen and touch alike); the canvas needs `touch-action: none`
 * so the browser does not claim pinch/scroll first. All updates go to the session store's
 * view; the canvas subscribes and redraws.
 */
export function useCanvasGestures(canvasRef: RefObject<HTMLCanvasElement | null>, getGeometry: () => Geometry): void {
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const pointers = new Map<number, { x: number; y: number }>();
    let lastPinch: number | null = null;

    const frac = (clientX: number, g: Geometry) => {
      const rect = canvas.getBoundingClientRect();
      return (clientX - rect.left - g.plotLeft) / Math.max(1, g.plotWidth);
    };
    const apply = (next: ReturnType<typeof zoomAt>) => useSession.getState().setView(next);

    const onWheel = (e: WheelEvent) => {
      const g = getGeometry();
      if (!g.rec) return;
      e.preventDefault();
      const factor = e.deltaY < 0 ? 1 / WHEEL_STEP : WHEEL_STEP;
      apply(zoomAt(useSession.getState().view, g.rec, factor, frac(e.clientX, g), g.plotWidth));
    };
    const onDown = (e: PointerEvent) => {
      if (e.button !== 0 && e.pointerType === "mouse") return;
      pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
      canvas.setPointerCapture?.(e.pointerId);
      if (pointers.size === 2) {
        const [a, b] = Array.from(pointers.values());
        lastPinch = Math.abs(a.x - b.x);
      } else lastPinch = null;
    };
    const onMove = (e: PointerEvent) => {
      const prev = pointers.get(e.pointerId);
      if (!prev) return;
      const g = getGeometry();
      pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
      if (!g.rec) return;
      if (pointers.size >= 2) {
        const [a, b] = Array.from(pointers.values());
        const dist = Math.abs(a.x - b.x);
        if (lastPinch !== null && dist > 0 && lastPinch > 0) {
          const midFrac = frac((a.x + b.x) / 2, g);
          apply(zoomAt(useSession.getState().view, g.rec, lastPinch / dist, midFrac, g.plotWidth));
        }
        lastPinch = dist;
        return;
      }
      const view = useSession.getState().view;
      if (!view) return; // fitted: nothing to pan
      const dxFrac = (e.clientX - prev.x) / Math.max(1, g.plotWidth);
      apply(pan(view, g.rec, -dxFrac * view.tSpan, g.plotWidth)); // content follows the pointer
    };
    const onUp = (e: PointerEvent) => {
      pointers.delete(e.pointerId);
      canvas.releasePointerCapture?.(e.pointerId);
      if (pointers.size < 2) lastPinch = null;
    };
    const onDouble = () => useSession.getState().setView(null);

    canvas.addEventListener("wheel", onWheel, { passive: false });
    canvas.addEventListener("pointerdown", onDown);
    canvas.addEventListener("pointermove", onMove);
    canvas.addEventListener("pointerup", onUp);
    canvas.addEventListener("pointercancel", onUp);
    canvas.addEventListener("dblclick", onDouble);
    return () => {
      canvas.removeEventListener("wheel", onWheel);
      canvas.removeEventListener("pointerdown", onDown);
      canvas.removeEventListener("pointermove", onMove);
      canvas.removeEventListener("pointerup", onUp);
      canvas.removeEventListener("pointercancel", onUp);
      canvas.removeEventListener("dblclick", onDouble);
    };
  }, [canvasRef, getGeometry]);
}
