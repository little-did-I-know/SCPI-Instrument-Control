import { api } from "../../api/client";
import { useSession } from "../../store/session";

const style = { fontSize: "var(--text-sm)", fontFamily: "var(--font-ui)", padding: "6px 12px", borderRadius: "var(--lc-radius-sm)", border: "1px solid var(--lc-border-strong)", color: "var(--lc-text)", textDecoration: "none" } as const;

export function ScreenshotButton() {
  const session = useSession((s) => s.session);
  if (!session) return <span style={{ ...style, color: "var(--lc-muted)", opacity: 0.6 }}>Screenshot</span>;
  return (
    <a href={api.screenshotUrl(session.id)} download style={style}>
      Screenshot
    </a>
  );
}
