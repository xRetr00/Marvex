import { useEffect, useState } from "react";
import { ChatApp } from "./surfaces/ChatApp";
import { OverlaySurface } from "./surfaces/overlay";
import { ControlLoaderSurface } from "./surfaces/ControlLoader";
import { SetupPage } from "./surfaces/Setup";
import { isSetupDone, getPersistedMode } from "./lib/modeStore";
import { showChat, showOverlay } from "./lib/shellCommands";

export function App() {
  const path = window.location.pathname;
  if (path.includes("overlay")) return <OverlaySurface />;
  if (path.includes("control-loader")) return <ControlLoaderSurface />;

  return <RootApp />;
}

function RootApp() {
  const [setupDone, setSetupDone] = useState(() => isSetupDone());

  // On boot, reflect the persisted top-level mode at the window level. During
  // first-run setup we force the chat window visible so setup is reachable.
  useEffect(() => {
    if (!setupDone) {
      void showChat().catch(() => undefined);
      return;
    }
    if (getPersistedMode() === "overlay") void showOverlay().catch(() => undefined);
    else void showChat().catch(() => undefined);
  }, [setupDone]);

  if (!setupDone) {
    return <SetupPage onComplete={() => setSetupDone(true)} />;
  }

  return <ChatApp />;
}
