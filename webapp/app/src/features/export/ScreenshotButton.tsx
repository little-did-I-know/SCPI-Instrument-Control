import { useState } from "react";
import { ApiError, api } from "../../api/client";
import { downloadAuthenticated } from "../../api/download";
import { useSession } from "../../store/session";

const style = { fontSize: "var(--text-sm)", fontFamily: "var(--font-ui)", padding: "6px 12px", borderRadius: "var(--lc-radius-sm)", border: "1px solid var(--lc-border-strong)", color: "var(--lc-text)", background: "transparent", cursor: "pointer" } as const;

export function ScreenshotButton() {
  const session = useSession((s) => s.session);
  const [error, setError] = useState<string | null>(null);

  if (!session) return <span style={{ ...style, color: "var(--lc-muted)", opacity: 0.6 }}>Screenshot</span>;

  async function handleClick() {
    if (!session) return;
    setError(null);
    try {
      await downloadAuthenticated(api.screenshotUrl(session.id), "screenshot.png");
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : String(err));
    }
  }

  return (
    <>
      <button type="button" onClick={handleClick} style={style}>
        Screenshot
      </button>
      {error && <div role="alert" style={{ color: "var(--danger)", fontSize: "var(--text-sm)" }}>{error}</div>}
    </>
  );
}
