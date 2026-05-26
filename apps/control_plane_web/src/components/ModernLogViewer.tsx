import { useMemo, useState } from "react";
import { LazyLog } from "@melloware/react-logviewer";
import { Search } from "lucide-react";
import { Card, CardContent } from "./ui/card";

export type LogTail = {
  name: string;
  source?: string;
  lines: string[];
};

export function ModernLogViewer({ logs }: { logs: LogTail[] }) {
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
    return <Card><CardContent className="p-4 text-sm text-muted-foreground">No log events exposed by the Control Plane API yet.</CardContent></Card>;
  }

  return (
    <Card className="overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border p-3">
        <div className="flex flex-wrap gap-2" aria-label="Log files">
          {logs.map((log) => (
            <button
              key={log.name}
              type="button"
              onClick={() => setActiveName(log.name)}
              className={log.name === activeLog.name ? activeTabClass : tabClass}
            >
              {log.name}
            </button>
          ))}
        </div>
        <label className="flex h-9 min-w-56 items-center gap-2 rounded-md border border-border bg-background px-3 text-muted-foreground">
          <Search size={15} />
          <input
            className="w-full bg-transparent text-sm text-foreground outline-none"
            placeholder="Search logs"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </label>
      </div>
      <div className="flex justify-between border-b border-border px-3 py-2 text-xs text-muted-foreground">
        <span>{activeLog.source ?? "control_plane_api"}</span>
        <span>{lineLabel}</span>
      </div>
      <div className="min-h-80 bg-background">
        <ol aria-label="Selected log text" className="absolute -m-px h-px w-px overflow-hidden border-0 p-0 [clip:rect(0,0,0,0)]">
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
          height={360}
          rowHeight={20}
          style={{ background: "transparent", color: "hsl(var(--foreground))", fontFamily: "ui-monospace, SFMono-Regular, Consolas, monospace", fontSize: 12 }}
          containerStyle={{ background: "transparent" }}
        />
      </div>
    </Card>
  );
}

const tabClass = "h-8 rounded-md border border-border bg-background px-3 text-xs text-muted-foreground transition-colors hover:bg-muted";
const activeTabClass = "h-8 rounded-md border border-primary bg-primary px-3 text-xs text-primary-foreground transition-colors";
