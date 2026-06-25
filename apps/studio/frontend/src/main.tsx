import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App.tsx";
import { wireAutosave } from "./app/autosave.ts";
import { wirePlayback } from "./app/wiring.ts";
import "./ui/theme/themes.css";
import "./ui/ui.css";

wirePlayback();
wireAutosave();

const root = document.getElementById("root");
if (!root) {
  throw new Error("#root not found");
}

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
