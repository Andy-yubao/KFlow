import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "@xyflow/react/dist/style.css";

import App from "./App";
import { ProjectProvider } from "./state/ProjectContext";
import "./styles.css";

const root = document.getElementById("root");
if (root === null) {
  throw new Error("KFlow UI root element is missing.");
}

createRoot(root).render(
  <StrictMode>
    <ProjectProvider>
      <App />
    </ProjectProvider>
  </StrictMode>,
);
