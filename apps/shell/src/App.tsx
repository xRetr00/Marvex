import { lazy, Suspense, useEffect, useState } from "react";
import { isSetupDone, getPersistedMode } from "./lib/modeStore";
import { showChat, showOverlay } from "./lib/shellCommands";

const ChatApp = lazy(() => import("./surfaces/ChatApp").then((module) => ({ default: module.ChatApp })));
const OverlaySurface = lazy(() => import("./surfaces/overlay").then((module) => ({ default: module.OverlaySurface })));
const ControlLoaderSurface = lazy(() => import("./surfaces/ControlLoader").then((module) => ({ default: module.ControlLoaderSurface })));
const SetupPage = lazy(() => import("./surfaces/Setup").then((module) => ({ default: module.SetupPage })));

function SurfaceFallback() {
  return <div style={{ minHeight: "100vh", background: "#020617" }} />;
}

export function App() {
  const path = window.location.pathname;
  if (path.includes("overlay")) {
    return (
      <Suspense fallback={<SurfaceFallback />}>
        <OverlaySurface />
      </Suspense>
    );
  }
  if (path.includes("control-loader")) {
    return (
      <Suspense fallback={<SurfaceFallback />}>
        <ControlLoaderSurface />
      </Suspense>
    );
  }

  return (
    <Suspense fallback={<SurfaceFallback />}>
      <RootApp />
    </Suspense>
  );
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
