/**
 * Heuristic parser that turns a plain assistant response into rich UI blocks so
 * the chat can render product cards, image/expandable cards, plans and alerts —
 * without the backend having to emit structured payloads yet. Conservative by
 * design: short/greeting replies stay a single plain text block (no cards for
 * "hi how are you"), and a structured fenced block always wins when present.
 */

export interface ParsedProduct {
  title: string;
  price: number;
  currency: string;
  originalPrice?: number;
  rating?: number;
  badge?: string;
  image: string;
}

export interface PlanStep {
  id: string;
  title: string;
}

export type RichBlock =
  | { type: "text"; text: string }
  | { type: "products"; products: ParsedProduct[] }
  | { type: "image"; src: string; title: string; description: string }
  | { type: "plan"; steps: PlanStep[] }
  | { type: "alert"; label: string };

const TRIVIAL_MAX_LEN = 140;
const GREETING = /^(hi|hello|hey|yo|thanks|thank you|ok|okay|got it|sure|yes|no|np|you'?re welcome|hello!|how are you|i'?m (good|fine|well))\b/i;

/** A short, conversational reply that should NOT be decorated with cards. */
export function isTrivialReply(text: string): boolean {
  const trimmed = text.trim();
  if (!trimmed) return true;
  const lines = trimmed.split(/\n+/).filter(Boolean);
  if (lines.length <= 2 && trimmed.length <= TRIVIAL_MAX_LEN && GREETING.test(trimmed)) return true;
  return false;
}

/** Deterministic gradient placeholder so product/image cards never break on a missing asset. */
export function placeholderImage(seed: string): string {
  let hash = 0;
  for (let i = 0; i < seed.length; i++) hash = (hash * 31 + seed.charCodeAt(i)) & 0xffff;
  const hue = hash % 360;
  const initial = (seed.trim()[0] ?? "M").toUpperCase();
  const svg = `<svg xmlns='http://www.w3.org/2000/svg' width='320' height='320'><defs><linearGradient id='g' x1='0' y1='0' x2='1' y2='1'><stop offset='0' stop-color='hsl(${hue},60%,28%)'/><stop offset='1' stop-color='hsl(${(hue + 40) % 360},70%,16%)'/></linearGradient></defs><rect width='320' height='320' fill='url(#g)'/><text x='50%' y='54%' font-family='Inter,sans-serif' font-size='140' fill='rgba(255,255,255,0.85)' text-anchor='middle' dominant-baseline='middle'>${initial}</text></svg>`;
  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
}

const IMAGE_RE = /!\[([^\]]*)\]\((https?:[^)\s]+)\)/g;
// "- Dell XPS 15 — $1,299" / "1. MacBook Air: $999 (4.5 stars)"
const PRODUCT_LINE_RE = /^\s*(?:[-*•]|\d+[.)])\s+(.+?)\s*[—:\-]\s*\$?\s*([\d][\d,]*(?:\.\d+)?)\b(?:.*?(\d(?:\.\d)?)\s*(?:stars?|\/\s*5))?/i;
const PLAN_HEADER_RE = /\b(here'?s? (?:the|my) plan|the plan|plan:|steps?:|i'?ll (?:do|proceed)|i will|first[, ]|step \d)\b/i;
const PLAN_STEP_RE = /^\s*(?:[-*•]|\d+[.)])\s+(.{3,})$/;
const ALERT_LINE_RE = /^\s*(?:⚠️?|reminder|alert|heads up|don'?t forget|note)\b[:\-]?\s*(.+)$/i;

function parseProducts(text: string): ParsedProduct[] {
  const products: ParsedProduct[] = [];
  for (const line of text.split(/\n+/)) {
    const m = line.match(PRODUCT_LINE_RE);
    if (!m) continue;
    const title = m[1].replace(/\*\*/g, "").trim();
    const price = Number.parseFloat(m[2].replace(/,/g, ""));
    if (!title || Number.isNaN(price)) continue;
    const rating = m[3] ? Number.parseFloat(m[3]) : undefined;
    products.push({ title, price, currency: "$", rating, image: placeholderImage(title) });
  }
  return products;
}

function parsePlanSteps(text: string): PlanStep[] {
  if (!PLAN_HEADER_RE.test(text)) return [];
  const steps: PlanStep[] = [];
  for (const line of text.split(/\n+/)) {
    if (PRODUCT_LINE_RE.test(line)) return []; // prices => it's a product list, not a plan
    const m = line.match(PLAN_STEP_RE);
    if (m) steps.push({ id: `step-${steps.length + 1}`, title: m[1].replace(/\*\*/g, "").trim() });
  }
  return steps.length >= 2 ? steps : [];
}

/** Parse an assistant response into ordered rich blocks. */
export function parseRichResponse(text: string): RichBlock[] {
  const trimmed = text.trim();
  if (isTrivialReply(trimmed)) return [{ type: "text", text: trimmed }];

  const blocks: RichBlock[] = [];

  // 1. Images -> expandable image cards (and strip them from the prose).
  let prose = trimmed;
  const images = [...trimmed.matchAll(IMAGE_RE)];
  for (const img of images) {
    blocks.push({ type: "image", src: img[2], title: img[1] || "Image", description: "" });
  }
  prose = prose.replace(IMAGE_RE, "").trim();

  // 2. Products (need at least 2 priced items to count as a product result).
  const products = parseProducts(prose);
  if (products.length >= 2) {
    const lead = prose.split(/\n/).find((l) => !PRODUCT_LINE_RE.test(l) && l.trim());
    if (lead) blocks.push({ type: "text", text: lead.trim() });
    blocks.push({ type: "products", products });
    return blocks;
  }

  // 3. Plan / steps.
  const steps = parsePlanSteps(prose);
  if (steps.length >= 2) {
    const lead = prose.split(/\n/).find((l) => !PLAN_STEP_RE.test(l) && l.trim());
    if (lead) blocks.push({ type: "text", text: lead.trim() });
    blocks.push({ type: "plan", steps });
    return blocks;
  }

  // 4. Alerts/reminders inline.
  const alertLines: string[] = [];
  const rest: string[] = [];
  for (const line of prose.split(/\n/)) {
    const m = line.match(ALERT_LINE_RE);
    if (m) alertLines.push(m[1].trim());
    else rest.push(line);
  }
  const restText = rest.join("\n").trim();
  if (restText) blocks.push({ type: "text", text: restText });
  for (const label of alertLines) blocks.push({ type: "alert", label });

  if (blocks.length === 0) blocks.push({ type: "text", text: trimmed });
  return blocks;
}
