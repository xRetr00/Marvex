import { useEffect, useRef, useState } from "react";
import { useBackendStatus } from "@/lib/backendStatus";
import { startBackend } from "@/lib/shellCommands";
import { StartupScreen } from "@/components/marvex/StartupScreen";

const CONTROL_PLANE_URL = "http://127.0.0.1:8766/";

/**
 * Gate for the Control Plane window: shows the shared startup/status screen
 * (bring-up + errors) until the backend is ready, then navigates this window to
 * the control plane server. The window's initialization script injects the
 * bearer token on the destination origin, so the SPA authenticates.
 */
export function ControlLoaderSurface() {
  const backend = useBackendStatus();
  const navigatedRef = useRef(false);
  const [helloDone, setHelloDone] = useState(false);

  useEffect(() => {
    if (backend?.ready && helloDone && !navigatedRef.current) {
      navigatedRef.current = true;
      const t = setTimeout(() => {
        window.location.href = CONTROL_PLANE_URL;
      }, 300);
      return () => clearTimeout(t);
    }
  }, [backend?.ready, helloDone]);

  return (
    <StartupScreen
      backend={backend}
      title="Control Plane"
      onHelloDone={() => setHelloDone(true)}
      onRetry={() => void startBackend().catch(() => undefined)}
    />
  );
}
