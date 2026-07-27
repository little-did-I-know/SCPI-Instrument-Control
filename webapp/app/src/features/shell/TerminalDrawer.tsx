import { useEffect } from "react";
import { TerminalPanel } from "../terminal/TerminalPanel";
import { useTerminalDrawer } from "./useTerminalDrawer";

/** The SCPI console, for every instrument kind. Full window width rather than a
 *  280px rail column, which is why it is a drawer and not a tab. */
export function TerminalDrawer() {
  const open = useTerminalDrawer((s) => s.open);
  const close = useTerminalDrawer((s) => s.close);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") close();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, close]);

  if (!open) return null;
  return (
    <section
      aria-label="SCPI terminal"
      style={{ height: "220px", flexShrink: 0, borderTop: "1px solid var(--lc-border)", paddingTop: "var(--space-3)" }}
    >
      <TerminalPanel />
    </section>
  );
}
