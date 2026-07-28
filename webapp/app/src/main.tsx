import React from "react";
import ReactDOM from "react-dom/client";
import "@design/styles.css";
import "./ds/ds.css";
import App from "./App";
import { captureTokenFromUrl, redeemInviteFromUrl } from "./api/token";

captureTokenFromUrl();

// Render only once any invitation in the URL has been exchanged, so the gate
// sees the token this load just obtained rather than briefly demanding one.
void redeemInviteFromUrl().finally(() => {
  ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>,
  );
});
