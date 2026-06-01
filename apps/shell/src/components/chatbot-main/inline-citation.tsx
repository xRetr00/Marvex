import type { CitationRef } from "@/lib/localTurn";

export function InlineCitation({ index, citation }: { index: number; citation?: CitationRef }) {
  const label = citation?.domain || hostname(citation?.url) || `source ${index}`;
  const openSource = () => {
    if (citation?.url) window.open(citation.url, "_blank", "noopener,noreferrer");
  };
  return (
    <span className="group relative inline-flex align-baseline">
      <button
        type="button"
        className="mx-0.5 inline-flex h-5 items-center gap-1 rounded-full border border-border/70 bg-secondary/90 px-1.5 text-[10px] font-medium leading-none text-foreground shadow-[var(--shadow-card)] hover:border-primary/60 hover:bg-primary/15"
        aria-label={`Citation ${index}: ${label}`}
        onClick={openSource}
      >
        {citation?.domain || citation?.url ? label : index}
      </button>
      <span className="pointer-events-none absolute bottom-full left-1/2 z-20 mb-2 hidden w-72 -translate-x-1/2 rounded-lg border border-border bg-popover p-3 text-left text-xs text-popover-foreground shadow-[var(--shadow-float)] group-hover:block group-focus-within:block">
        <strong className="block truncate text-foreground">{citation?.title || label}</strong>
        {citation?.url ? <span className="mt-1 block truncate text-muted-foreground">{citation.url}</span> : null}
        {citation?.snippet ? <span className="mt-2 block leading-relaxed text-muted-foreground">{citation.snippet}</span> : null}
      </span>
    </span>
  );
}

function hostname(url?: string): string {
  if (!url) return "";
  try {
    return new URL(url).hostname;
  } catch {
    return "";
  }
}
