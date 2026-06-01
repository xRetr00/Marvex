import { Streamdown, type Components } from "streamdown";
import { cn } from "@/lib/utils";

function fixNumberedListBreaks(text: string): string {
  return text.replace(/^(\d+)\.\s*\n+\s*\n*/gm, "$1. ");
}

const CODE_FENCE_LANGS = new Set([
  "bash",
  "diff",
  "html",
  "js",
  "json",
  "jsx",
  "md",
  "markdown",
  "powershell",
  "py",
  "python",
  "sh",
  "shell",
  "text",
  "ts",
  "tsx",
  "yml",
  "yaml",
]);

function normalizeCodeFenceLanguages(text: string): string {
  return text.replace(/```([^\n]*)/g, (_match, langRaw) => {
    const lang = String(langRaw || "").trim().toLowerCase();
    if (!lang) return "```";
    const normalized = lang.split(/\s+/)[0];
    return CODE_FENCE_LANGS.has(normalized) ? `\`\`\`${normalized}` : "```text";
  });
}

export type ChatbotMarkdownProps = {
  content: string;
  className?: string;
};

const components: Components = {
  h1: ({ children, ...props }) => (
    <h1 className="mt-3 mb-1.5 text-base font-semibold text-foreground" {...props}>
      {children}
    </h1>
  ),
  h2: ({ children, ...props }) => (
    <h2 className="mt-3 mb-1.5 text-base font-semibold text-foreground" {...props}>
      {children}
    </h2>
  ),
  h3: ({ children, ...props }) => (
    <h3 className="mt-2 mb-1 text-sm font-semibold text-foreground" {...props}>
      {children}
    </h3>
  ),
  h4: ({ children, ...props }) => (
    <h4 className="mt-2 mb-1 text-sm font-medium text-foreground" {...props}>
      {children}
    </h4>
  ),
  p: ({ children, ...props }) => (
    <p className="text-sm leading-relaxed text-foreground/88" {...props}>
      {children}
    </p>
  ),
  ul: ({ children, ...props }) => (
    <ul className="mb-2 list-outside list-disc space-y-0.5 pl-4 text-sm text-foreground/88" {...props}>
      {children}
    </ul>
  ),
  ol: ({ children, ...props }) => (
    <ol className="mb-2 list-outside list-decimal space-y-0.5 pl-5 text-sm text-foreground/88" {...props}>
      {children}
    </ol>
  ),
  li: ({ children, ...props }) => (
    <li className="pl-0.5 text-sm text-foreground/88" {...props}>
      {children}
    </li>
  ),
  strong: ({ children, ...props }) => (
    <strong className="font-semibold text-foreground" {...props}>
      {children}
    </strong>
  ),
  a: ({ href, children, ...props }) => {
    if (!href) return <span>{children}</span>;
    const isExternal = href.startsWith("http") || href.startsWith("mailto:");
    return (
      <a
        {...props}
        className="text-chart-2 underline-offset-2 hover:underline"
        href={href}
        rel={isExternal ? "noopener noreferrer" : undefined}
        target={isExternal ? "_blank" : undefined}
      >
        {children}
      </a>
    );
  },
  blockquote: ({ children, ...props }) => (
    <blockquote className="mb-2 border-l-2 border-border pl-3 text-sm text-muted-foreground" {...props}>
      {children}
    </blockquote>
  ),
  code: ({ children, ...props }) => (
    <code className="rounded-md border border-border/60 bg-muted/60 px-1.5 py-0.5 font-mono text-[0.85em] text-foreground" {...props}>
      {children}
    </code>
  ),
  pre: ({ children, ...props }) => (
    <pre className="my-2 overflow-x-auto rounded-lg border border-border/70 bg-background/90 p-3 text-xs leading-relaxed" {...props}>
      {children}
    </pre>
  ),
  table: ({ children, ...props }) => (
    <div className="my-3 overflow-x-auto rounded-lg border border-border/70">
      <table className="w-full text-sm" {...props}>
        {children}
      </table>
    </div>
  ),
  th: ({ children, ...props }) => (
    <th className="bg-muted px-3 py-2 text-left font-medium text-foreground" {...props}>
      {children}
    </th>
  ),
  td: ({ children, ...props }) => (
    <td className="border-t border-border/70 px-3 py-2 text-foreground/84" {...props}>
      {children}
    </td>
  ),
};

export function ChatbotMarkdown({ content, className }: ChatbotMarkdownProps) {
  const safeContent = normalizeCodeFenceLanguages(fixNumberedListBreaks(content));
  return (
    <div className={cn("overflow-hidden break-words [&_li>p]:inline [&_li>p]:mb-0", className)}>
      <Streamdown components={components}>
        {safeContent}
      </Streamdown>
    </div>
  );
}
