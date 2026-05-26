import { lazy, Suspense, useEffect, useLayoutEffect, useState, type ReactNode } from "react";
import { ErrorBoundary, type FallbackProps } from "react-error-boundary";
import { isSetupDone, getPersistedMode } from "./lib/modeStore";
import { showChat, showOverlay } from "./lib/shellCommands";
import "./surfaces/overlay.css";

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

function OverlayFallback() {
  return (
    <div
      className="overlay-shell"
      style={{
        width: 124,
        height: 52,
        display: "grid",
        placeItems: "center",
        background: "transparent",
      }}
    >
      <div
        style={{
          width: 124,
          height: 52,
          borderRadius: 30,
          background: "#000",
          display: "grid",
          placeItems: "center",
          color: "#ffe0c2",
          fontSize: 11,
          fontWeight: 650,
        }}
      >
        Marvex
      </div>
    </div>
  );
}

function SurfaceErrorFallback({ error }: Partial<FallbackProps>) {
  const message = error instanceof Error ? error.message : "Restart Marvex. If this returns, rebuild the shell assets and check the app log.";

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
          {message}
        </span>
      </div>
    </div>
  );
}

function OverlayErrorFallback() {
  return (
    <div className="overlay-shell" role="alert" style={{ width: 124, height: 52, background: "transparent" }}>
      <div style={{ width: 124, height: 52, borderRadius: 30, background: "#000", display: "grid", placeItems: "center", color: "#e54d2e", fontSize: 11, fontWeight: 700 }}>
        Error
      </div>
    </div>
  );
}

function NotFoundPage({ path }: { path: string }) {
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
      <div style={{ width: "min(440px, calc(100vw - 32px))", display: "grid", gap: 10, textAlign: "center" }}>
        <strong style={{ fontSize: 16 }}>Window not found</strong>
        <code style={{ color: "var(--muted-foreground, #b4b4b4)", fontSize: 12 }}>{path}</code>
      </div>
    </div>
  );
}

function OverlayDocumentScope({ children }: { children: ReactNode }) {
  useLayoutEffect(() => {
    document.documentElement.classList.add("marvex-overlay-document");
    document.body.classList.add("marvex-overlay-document");
    document.getElementById("root")?.classList.add("marvex-overlay-root");
    return () => {
      document.documentElement.classList.remove("marvex-overlay-document");
      document.body.classList.remove("marvex-overlay-document");
      document.getElementById("root")?.classList.remove("marvex-overlay-root");
    };
  }, []);
  return children;
}

export function App() {
  const path = window.location.pathname;
  if (path.includes("overlay")) {
    return (
      <OverlayDocumentScope>
        <ErrorBoundary FallbackComponent={OverlayErrorFallback}>
          <Suspense fallback={<OverlayFallback />}>
            <OverlaySurface />
          </Suspense>
        </ErrorBoundary>
      </OverlayDocumentScope>
    );
  }
  if (path.includes("control-loader")) {
    return (
      <ErrorBoundary FallbackComponent={SurfaceErrorFallback}>
        <Suspense fallback={<SurfaceFallback />}>
          <ControlLoaderSurface />
        </Suspense>
      </ErrorBoundary>
    );
  }
  if (path !== "/" && path !== "") return <NotFoundPage path={path} />;

  return (
    <ErrorBoundary FallbackComponent={SurfaceErrorFallback}>
      <Suspense fallback={<SurfaceFallback />}>
        <RootApp />
      </Suspense>
    </ErrorBoundary>
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
