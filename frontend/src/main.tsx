import "./intl-guard"; // MUST run before any uPlot import (module-init Intl crash)

import React from "react";
import ReactDOM from "react-dom/client";

import App from "./App";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
