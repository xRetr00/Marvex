import { ChatApp } from "./surfaces/ChatApp";
import { OverlaySurface } from "./surfaces/overlay";
import { SpotlightSurface } from "./surfaces/Spotlight";

export function App() {
  const path = window.location.pathname;
  if (path.includes("overlay")) return <OverlaySurface />;
  if (path.includes("spotlight")) return <SpotlightSurface />;
  return <ChatApp />;
}
