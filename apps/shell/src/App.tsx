import { useState } from "react";
import { ChatApp } from "./surfaces/ChatApp";
import { OverlaySurface } from "./surfaces/overlay";
import { SpotlightSurface } from "./surfaces/Spotlight";
import { SetupPage } from "./surfaces/Setup";
import { getPersistedMode, persistMode, isSetupDone, type AppMode } from "./lib/modeStore";

export function App() {
  const path = window.location.pathname;
  if (path.includes("overlay")) return <OverlaySurface />;
  if (path.includes("spotlight")) return <SpotlightSurface />;

  return <RootApp />;
}

function RootApp() {
  const [setupDone, setSetupDone] = useState(() => isSetupDone());
  const [mode, setMode] = useState<AppMode>(() => getPersistedMode());

  function handleSetupComplete() {
    setSetupDone(true);
  }

  function handleModeChange(newMode: AppMode) {
    persistMode(newMode);
    setMode(newMode);
  }

  if (!setupDone) {
    return <SetupPage onComplete={handleSetupComplete} />;
  }

  if (mode === "overlay") {
    return <OverlaySurface />;
  }

  return <ChatApp mode={mode} onModeChange={handleModeChange} />;
}
