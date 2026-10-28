import { createRoot } from "react-dom/client";
import ReleaseApp from "./release/PublicReleaseApp";
import "./release/public-release.css";

if (import.meta.env.MODE === "demo") {
  void import("./release/LocalDemo").then(({default: LocalDemo}) => createRoot(document.getElementById("root")!).render(<LocalDemo />));
} else {
  createRoot(document.getElementById("root")!).render(<ReleaseApp />);
}
