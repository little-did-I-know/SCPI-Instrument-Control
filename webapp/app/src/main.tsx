import React from "react";
import ReactDOM from "react-dom/client";
import "@design/styles.css";
import "./ds/ds.css";
import App from "./App";
import { captureTokenFromUrl } from "./api/token";

captureTokenFromUrl();

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
