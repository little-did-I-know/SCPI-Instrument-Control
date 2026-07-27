import { useSession } from "../../store/session";

/** Session-level failures, which arrive unprompted: an error frame from the
 *  server, or a stream that dropped. Panels keep their own alert regions for
 *  failures of a write the user just made -- different things, both needed.
 *
 *  role="alert" so a screen reader announces it on arrival, which is the case
 *  this exists for: a connection lost part-way through a capture. */
export function ErrorBanner() {
  const error = useSession((s) => s.error);
  const dismiss = useSession((s) => s.dismissError);
  if (error === null) return null;
  return (
    <div
      role="alert"
      style={{
        display: "flex",
        alignItems: "center",
        gap: "var(--space-3)",
        padding: "8px 14px",
        background: "color-mix(in srgb, var(--danger) 12%, transparent)",
        color: "var(--danger)",
        borderBottom: "1px solid var(--lc-border)",
        fontSize: "var(--text-sm)",
      }}
    >
      <span aria-hidden>⚠</span>
      <span style={{ flex: 1 }}>{error}</span>
      <button
        type="button"
        onClick={dismiss}
        style={{ fontSize: "var(--text-sm)", fontFamily: "var(--font-ui)", padding: "2px 10px", borderRadius: "var(--lc-radius-sm)", border: "1px solid currentColor", color: "inherit", background: "transparent", cursor: "pointer" }}
      >
        Dismiss
      </button>
    </div>
  );
}
