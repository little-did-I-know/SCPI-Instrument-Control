import React from "react";
import ReactDOM from "react-dom/client";
import "@design/styles.css";
import "../ds/ds.css";
import { App } from "./App";

// No captureTokenFromUrl() and no <TokenGate> here, unlike the LAN app's
// main.tsx -- that is deliberate, not an omission. This bundle is served only
// by the admin listener, which binds 127.0.0.1, so there is no credential to
// collect: reaching this page at all is the proof of access. A gate here would
// only imply a permission model that does not exist. See
// scpi_control/server/admin/app.py for the two defences that do the work.
ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
