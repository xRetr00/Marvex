// Maps a tool/capability call into a friendly Chain-of-Thought step label,
// e.g. file.search -> "Searching <query>" (active) / "Searched <query>" (done),
// matching the screenshots ("Grepped …", "Read ContextMenu.tsx", "Searching").

export interface ActivityStep {
  id: string;
  name: string;
  /** Raw JSON arguments string from the tool call, if any. */
  arguments?: string;
  /** Whether the step is still running. */
  active: boolean;
}

interface VerbForms {
  /** present-continuous, shown while the step is active (e.g. "Searching"). */
  active: string;
  /** past tense, shown when the step is done (e.g. "Searched"). */
  done: string;
  /** which argument keys hold the human-readable target, in priority order. */
  targetKeys: string[];
}

const VERBS: Record<string, VerbForms> = {
  "file.search": { active: "Searching", done: "Searched", targetKeys: ["query", "substring", "path"] },
  "file.rg": { active: "Grepping", done: "Grepped", targetKeys: ["query", "name", "tokens", "path"] },
  "file.read": { active: "Reading", done: "Read", targetKeys: ["path", "file"] },
  "file.list": { active: "Listing", done: "Listed", targetKeys: ["path", "directory"] },
  "file.write": { active: "Editing", done: "Edited", targetKeys: ["path", "file"] },
  "file.patch": { active: "Patching", done: "Patched", targetKeys: ["path", "file"] },
  "web.search": { active: "Searching the web", done: "Searched the web", targetKeys: ["query", "q"] },
  "memory.search": { active: "Recalling", done: "Recalled", targetKeys: ["query"] },
  "memory.remember": { active: "Saving to memory", done: "Saved to memory", targetKeys: ["text", "content"] },
  "memory.forget": { active: "Forgetting", done: "Forgot", targetKeys: ["ref", "memory_ref"] },
  "memory.list_recent": { active: "Listing memory", done: "Listed memory", targetKeys: [] },
  "builtin.calculator": { active: "Calculating", done: "Calculated", targetKeys: ["expression"] },
  "builtin.time_date": { active: "Checking the time", done: "Checked the time", targetKeys: [] },
  "builtin.repo_status": { active: "Checking the repo", done: "Checked the repo", targetKeys: [] },
  "builtin.capability_diagnostics": { active: "Running diagnostics", done: "Ran diagnostics", targetKeys: [] },
  "builtin.playwright_browser": { active: "Browsing", done: "Browsed", targetKeys: ["url", "task"] },
  "playwright_mcp.task": { active: "Browsing", done: "Browsed", targetKeys: ["url", "task"] },
  "browser_use.task": { active: "Browsing", done: "Browsed", targetKeys: ["task", "url"] },
  "computer_use.action": { active: "Controlling the desktop", done: "Controlled the desktop", targetKeys: ["action", "task"] },
  "status.thinking": { active: "Thinking", done: "Thought", targetKeys: [] },
  "status.working": { active: "Working", done: "Worked", targetKeys: [] },
  "status.using_tools": { active: "Using tools", done: "Used tools", targetKeys: [] },
  "status.mcp": { active: "Connecting to MCP", done: "Used MCP", targetKeys: [] },
  "status.skills": { active: "Loading skills", done: "Loaded skills", targetKeys: [] },
  "status.searching_web": { active: "Searching the web", done: "Searched the web", targetKeys: [] },
  "status.asking": { active: "Preparing a question", done: "Prepared a question", targetKeys: [] },
  "status.needs_approval": { active: "Waiting for approval", done: "Approval handled", targetKeys: [] },
};

function normalizeName(name: string): string {
  // Tool calls may arrive with underscores (builtin_playwright_browser) or dots.
  return name.trim().replace(/_/g, ".").replace(/\.task$|\.action$/i, (m) => m);
}

function fallbackVerb(name: string): VerbForms {
  const pretty = name.replace(/[._-]+/g, " ").trim() || "tool";
  return { active: `Running ${pretty}`, done: `Ran ${pretty}`, targetKeys: [] };
}

function extractTarget(args: string | undefined, keys: string[]): string {
  if (!args) return "";
  let parsed: Record<string, unknown>;
  try {
    parsed = JSON.parse(args) as Record<string, unknown>;
  } catch {
    return "";
  }
  for (const key of keys) {
    const value = parsed[key];
    if (typeof value === "string" && value.trim()) {
      return shortenTarget(value.trim());
    }
  }
  // No known key: show the first short string value, if any.
  for (const value of Object.values(parsed)) {
    if (typeof value === "string" && value.trim()) return shortenTarget(value.trim());
  }
  return "";
}

function shortenTarget(value: string): string {
  // For path-like targets, show the basename; otherwise truncate long strings.
  const path = value.includes("/") || value.includes("\\") ? value.split(/[\\/]/).pop() ?? value : value;
  return path.length > 60 ? `${path.slice(0, 57)}…` : path;
}

/** Build the label for a tool step (verb + target), tense by active state. */
export function activityLabel(step: ActivityStep): string {
  const key = VERBS[step.name] ? step.name : normalizeName(step.name);
  const verb = VERBS[key] ?? fallbackVerb(step.name || key);
  const target = extractTarget(step.arguments, verb.targetKeys);
  const word = step.active ? verb.active : verb.done;
  return target ? `${word} ${target}` : word;
}
