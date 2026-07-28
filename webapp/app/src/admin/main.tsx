import React from "react";
import ReactDOM from "react-dom/client";
import "@design/styles.css";
import "../ds/ds.css";

// Placeholder root: the admin screens (People, invitations, etc.) are built in
// a later task. This entry point exists so the build in this task is
// verifiable end-to-end -- see webapp/app/vite.admin.config.ts.
function AdminPlaceholder() {
  return <div style={{ padding: "var(--space-3)", fontFamily: "var(--font-ui)" }}>SCPI Gateway Admin</div>;
}

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <AdminPlaceholder />
  </React.StrictMode>,
);
