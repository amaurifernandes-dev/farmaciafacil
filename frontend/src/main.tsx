import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import App from "./App";
import { SessaoProvider } from "./sessao";
import "./estilos.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <SessaoProvider>
        <App />
      </SessaoProvider>
    </BrowserRouter>
  </StrictMode>,
);

if ("serviceWorker" in navigator && import.meta.env.PROD) {
  navigator.serviceWorker.register("/sw.js").catch(() => undefined);
}
