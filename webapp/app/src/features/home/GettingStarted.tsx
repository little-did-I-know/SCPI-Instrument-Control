export function GettingStarted() {
  return (
    <details style={{ fontSize: "var(--text-sm)", color: "var(--lc-text)" }}>
      <summary style={{ cursor: "pointer", fontWeight: 600 }}>Getting started</summary>
      <ul style={{ margin: "var(--space-2) 0 0", paddingLeft: "var(--space-4)", color: "var(--lc-muted)" }}>
        <li>Find your instrument's IP (its Utility / I/O menu).</li>
        <li>Enable LAN / SCPI on the instrument.</li>
        <li>
          Explore the API at <a href="/docs">/docs</a>.
        </li>
        <li>No hardware? Start a <b>Mock scope</b>.</li>
      </ul>
    </details>
  );
}
