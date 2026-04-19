import React from "react";
import ReactDOM from "react-dom/client";

import { App } from "./App";
import { applyTheme, resolveInitialTheme } from "./theme";
import "./styles.css";

applyTheme(resolveInitialTheme());

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
