import { render } from "@testing-library/react";
import { useRef } from "react";
import { beforeEach, describe, expect, it } from "vitest";
import { useSession } from "../../store/session";
import { useCanvasGestures } from "./useCanvasGestures";

const REC = { t0: -0.007, dt: 1e-6, n: 14_001 };

function Harness() {
  const ref = useRef<HTMLCanvasElement | null>(null);
  useCanvasGestures(ref, () => ({ rec: REC, plotLeft: 0, plotWidth: 1400 }));
  return <canvas ref={ref} data-testid="c" />;
}

function fire(el: Element, type: string, init: Record<string, unknown>) {
  const ev = new Event(type, { bubbles: true, cancelable: true }) as Event & Record<string, unknown>;
  Object.assign(ev, init);
  el.dispatchEvent(ev);
  return ev;
}

beforeEach(() => useSession.getState().clearSession());

describe("useCanvasGestures", () => {
  it("wheel up zooms in about the pointer and prevents page scroll", () => {
    const { getByTestId } = render(<Harness />);
    const c = getByTestId("c");
    (c as HTMLCanvasElement).getBoundingClientRect = () => ({ left: 0, top: 0, width: 1400, height: 400 }) as DOMRect;
    const ev = fire(c, "wheel", { deltaY: -100, clientX: 350, clientY: 100 });
    const v = useSession.getState().view!;
    expect(v).not.toBeNull();
    expect(v.tSpan).toBeLessThan(0.014);
    expect(v.tCenter - v.tSpan / 2 + 0.25 * v.tSpan).toBeCloseTo(-0.0035, 9); // t under the pointer is unchanged
    expect(ev.defaultPrevented).toBe(true);
  });

  it("dragging pans by the dragged fraction of the span", () => {
    const { getByTestId } = render(<Harness />);
    const c = getByTestId("c");
    (c as HTMLCanvasElement).getBoundingClientRect = () => ({ left: 0, top: 0, width: 1400, height: 400 }) as DOMRect;
    (c as HTMLCanvasElement).setPointerCapture = () => {};
    (c as HTMLCanvasElement).releasePointerCapture = () => {};
    useSession.getState().setView({ tCenter: 0, tSpan: 0.007 });
    fire(c, "pointerdown", { pointerId: 1, clientX: 700, clientY: 100, button: 0, pointerType: "mouse" });
    fire(c, "pointermove", { pointerId: 1, clientX: 560, clientY: 100 }); // dragged 140 px left = 10% of the width
    fire(c, "pointerup", { pointerId: 1, clientX: 560, clientY: 100 });
    expect(useSession.getState().view!.tCenter).toBeCloseTo(0.0007, 9); // content follows the finger: window moves right
  });

  it("two pointers pinch-zoom about their midpoint", () => {
    const { getByTestId } = render(<Harness />);
    const c = getByTestId("c");
    (c as HTMLCanvasElement).getBoundingClientRect = () => ({ left: 0, top: 0, width: 1400, height: 400 }) as DOMRect;
    (c as HTMLCanvasElement).setPointerCapture = () => {};
    (c as HTMLCanvasElement).releasePointerCapture = () => {};
    fire(c, "pointerdown", { pointerId: 1, clientX: 600, clientY: 100, button: 0 });
    fire(c, "pointerdown", { pointerId: 2, clientX: 800, clientY: 100, button: 0 });
    fire(c, "pointermove", { pointerId: 2, clientX: 1000, clientY: 100 }); // spread 200 -> 400 px
    const v = useSession.getState().view!;
    expect(v.tSpan).toBeCloseTo(0.007, 6);
  });

  it("double-click resets to fitted", () => {
    const { getByTestId } = render(<Harness />);
    const c = getByTestId("c");
    useSession.getState().setView({ tCenter: 0, tSpan: 0.007 });
    fire(c, "dblclick", {});
    expect(useSession.getState().view).toBeNull();
  });

  it("does nothing without a record", () => {
    function NoRecord() {
      const ref = useRef<HTMLCanvasElement | null>(null);
      useCanvasGestures(ref, () => ({ rec: null, plotLeft: 0, plotWidth: 1400 }));
      return <canvas ref={ref} data-testid="c" />;
    }
    const { getByTestId } = render(<NoRecord />);
    fire(getByTestId("c"), "wheel", { deltaY: -100, clientX: 10, clientY: 10 });
    expect(useSession.getState().view).toBeNull();
  });
});
