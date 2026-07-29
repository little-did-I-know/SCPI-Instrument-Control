import { GroupBox } from "../ds/GroupBox";
import { People } from "./People";
import { Sessions } from "./Sessions";

/**
 * Admin app shell. There is exactly one screen -- the person who administers
 * the gateway sits down at the bench PC to manage access, not to navigate.
 */
export function App() {
  return (
    <div style={{ padding: "var(--space-4)", fontFamily: "var(--font-ui)", maxWidth: "960px", margin: "0 auto" }}>
      <header style={{ marginBottom: "var(--space-4)" }}>
        <h1 style={{ margin: 0, fontSize: "var(--text-lg)", fontWeight: "var(--weight-bold)" }}>SCPI Gateway Admin</h1>
        <p style={{ margin: "var(--space-1) 0 0", color: "var(--text-muted)", fontSize: "var(--text-sm)" }}>
          Access and live sessions for the gateway on this machine.
        </p>
      </header>
      <GroupBox>
        <People />
        <div style={{ marginTop: "var(--space-4)" }}>
          <Sessions />
        </div>
      </GroupBox>
    </div>
  );
}
