import { Component, lazy, Suspense, useEffect, useState, type ReactNode } from "react";
import { isSetupDone, getPersistedMode } from "./lib/modeStore";
import { showChat, showOverlay } from "./lib/shellCommands";

const ChatApp = lazy(() => import("./surfaces/ChatApp").then((module) => ({ default: module.ChatApp })));
const OverlaySurface = lazy(() => import("./surfaces/overlay").then((module) => ({ default: module.OverlaySurface })));
const ControlLoaderSurface = lazy(() => import("./surfaces/ControlLoader").then((module) => ({ default: module.ControlLoaderSurface })));
const SetupPage = lazy(() => import("./surfaces/Setup").then((module) => ({ default: module.SetupPage })));

function SurfaceFallback() {
  return (
    <div
      style={{
        minHeight: "100vh",
        display: "grid",
        placeItems: "center",
        background: "var(--background, #111111)",
        color: "var(--foreground, #eeeeee)",
        fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
      }}
    >
      <div style={{ display: "grid", gap: 8, textAlign: "center", padding: 24 }}>
        <strong style={{ fontSize: 14 }}>Loading Marvex...</strong>
        <span style={{ color: "var(--muted-foreground, #b4b4b4)", fontSize: 12 }}>Preparing the shell window.</span>
      </div>
    </div>
  );
}

function SurfaceErrorFallback() {
  return (
    <div
      role="alert"
      style={{
        minHeight: "100vh",
        display: "grid",
        placeItems: "center",
        background: "var(--background, #111111)",
        color: "var(--foreground, #eeeeee)",
        fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
      }}
    >
      <div style={{ width: "min(420px, calc(100vw - 32px))", display: "grid", gap: 10, textAlign: "center" }}>
        <strong style={{ fontSize: 15 }}>Marvex could not load this window.</strong>
        <span style={{ color: "var(--muted-foreground, #b4b4b4)", fontSize: 12, lineHeight: 1.5 }}>
          Restart Marvex. If this returns, rebuild the shell assets and check the app log.
        </span>
      </div>
    </div>
  );
}

class SurfaceErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  render() {
    if (this.state.failed) return <SurfaceErrorFallback />;
    return this.props.children;
  }
}

export function App() {
  const path = window.location.pathname;
  if (path.includes("overlay")) {
    return (
      <SurfaceErrorBoundary>
        <Suspense fallback={<SurfaceFallback />}>
          <OverlaySurface />
        </Suspense>
      </SurfaceErrorBoundary>
    );
  }
  if (path.includes("control-loader")) {
    return (
      <SurfaceErrorBoundary>
        <Suspense fallback={<SurfaceFallback />}>
          <ControlLoaderSurface />
        </Suspense>
      </SurfaceErrorBoundary>
    );
  }

  return (
    <SurfaceErrorBoundary>
      <Suspense fallback={<SurfaceFallback />}>
        <RootApp />
      </Suspense>
    </SurfaceErrorBoundary>
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
