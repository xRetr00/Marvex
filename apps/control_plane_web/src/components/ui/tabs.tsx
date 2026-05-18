import { cn } from "../../lib/utils";

export function TabButton({ active, children, onClick }: { active: boolean; children: React.ReactNode; onClick: () => void }) {
  return (
    <button
      type="button"
      className={cn(
        "flex h-9 w-full items-center justify-start rounded-md px-3 text-left text-sm transition-colors",
        active ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted hover:text-foreground"
      )}
      onClick={onClick}
    >
      {children}
    </button>
  );
}