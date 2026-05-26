import { useMemo, useState } from "react";
import type { CSSProperties, ReactNode } from "react";
import { LazyLog } from "@melloware/react-logviewer";
import { Search } from "lucide-react";
import type { LogTail } from "@/lib/shellCommands";

type ModernLogViewerProps = {
  logs: LogTail[];
};

export function ModernLogViewer({ logs }: ModernLogViewerProps) {
  const [activeName, setActiveName] = useState(logs[0]?.name ?? "");
  const [query, setQuery] = useState("");
  const activeLog = logs.find((log) => log.name === activeName) ?? logs[0];
  const filteredLines = useMemo(() => {
    const lines = activeLog?.lines ?? [];
    const needle = query.trim().toLowerCase();
    if (!needle) return lines;
    return lines.filter((line) => line.toLowerCase().includes(needle));
  }, [activeLog, query]);
  const lineLabel = `${filteredLines.length} ${filteredLines.length === 1 ? "line" : "lines"}`;

  if (!activeLog) {
    return <Muted>No log events exposed by the Control Plane API yet.</Muted>;
  }

  return (
    <section className="marvex-glass" style={panel}>
      <div style={toolbar}>
        <div style={tabs} aria-label="Log files">
          {logs.map((log) => (
            <button
              key={log.name}
              type="button"
              onClick={() => setActiveName(log.name)}
              style={{ ...tab, ...(log.name === activeLog.name ? activeTab : null) }}
            >
              {log.name}
            </button>
          ))}
        </div>
        <label style={searchBox}>
          <Search size={14} />
          <input
            placeholder="Search logs"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            style={searchInput}
          />
        </label>
      </div>
      <div style={meta}>
        <span>{activeLog.source ?? "control_plane_api"}</span>
        <span>{lineLabel}</span>
      </div>
      <div style={viewer}>
        <ol aria-label="Selected log text" style={screenReaderLog}>
          {(filteredLines.length ? filteredLines : ["(empty)"]).map((line, index) => (
            <li key={`${index}-${line}`}>{line}</li>
          ))}
        </ol>
        <LazyLog
          text={filteredLines.join("\n") || "(empty)"}
          enableSearch
          enableLineNumbers
          selectableLines
          follow
          height={300}
          rowHeight={20}
          style={{ background: "transparent", color: "var(--foreground)", fontFamily: "ui-monospace, SFMono-Regular, Consolas, monospace", fontSize: 11 }}
          containerStyle={{ background: "transparent" }}
        />
      </div>
    </section>
  );
}

function Muted({ children }: { children: ReactNode }) {
  return <span style={{ fontSize: 12, color: "var(--muted-foreground)" }}>{children}</span>;
}

const panel: CSSProperties = { borderRadius: 8, overflow: "hidden", display: "grid", gap: 0 };
const toolbar: CSSProperties = { display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, padding: 10, borderBottom: "1px solid var(--border)" };
const tabs: CSSProperties = { display: "flex", flexWrap: "wrap", gap: 6, minWidth: 0 };
const tab: CSSProperties = { height: 28, borderRadius: 7, border: "1px solid var(--border)", background: "var(--secondary)", color: "var(--muted-foreground)", padding: "0 9px", fontSize: 11, cursor: "pointer" };
const activeTab: CSSProperties = { background: "var(--primary)", color: "var(--primary-foreground)", borderColor: "var(--primary)" };
const searchBox: CSSProperties = { height: 30, minWidth: 190, display: "flex", alignItems: "center", gap: 7, borderRadius: 8, border: "1px solid var(--border)", background: "var(--background)", color: "var(--muted-foreground)", padding: "0 9px" };
const searchInput: CSSProperties = { width: "100%", border: 0, outline: 0, background: "transparent", color: "var(--foreground)", fontSize: 12 };
const meta: CSSProperties = { display: "flex", justifyContent: "space-between", gap: 10, padding: "8px 12px", borderBottom: "1px solid var(--border)", color: "var(--muted-foreground)", fontSize: 11 };
const viewer: CSSProperties = { minHeight: 260, background: "color-mix(in srgb, var(--background) 88%, #000)", padding: 0 };
const screenReaderLog: CSSProperties = { position: "absolute", width: 1, height: 1, padding: 0, margin: -1, overflow: "hidden", clip: "rect(0, 0, 0, 0)", border: 0 };
