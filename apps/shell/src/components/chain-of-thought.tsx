import { useControllableState } from "@radix-ui/react-use-controllable-state";
import { BrainIcon, ChevronDownIcon, DotIcon, type LucideIcon } from "lucide-react";
import type { ComponentProps, ReactNode } from "react";
import { createContext, memo, useContext, useMemo } from "react";
import { Badge } from "@/components/ui/badge";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { cn } from "@/lib/utils";

interface ChainOfThoughtContextValue {
  isOpen: boolean;
  setIsOpen: (open: boolean) => void;
}

const ChainOfThoughtContext = createContext<ChainOfThoughtContextValue | null>(null);

const useChainOfThought = () => {
  const ctx = useContext(ChainOfThoughtContext);
  if (!ctx) throw new Error("ChainOfThought components must be used within ChainOfThought");
  return ctx;
};

export type ChainOfThoughtProps = ComponentProps<"div"> & {
  open?: boolean;
  defaultOpen?: boolean;
  onOpenChange?: (open: boolean) => void;
};

export const ChainOfThought = memo(({ className, open, defaultOpen = false, onOpenChange, children, ...props }: ChainOfThoughtProps) => {
  const [isOpen, setIsOpen] = useControllableState({ prop: open, defaultProp: defaultOpen, onChange: onOpenChange });
  const ctx = useMemo(() => ({ isOpen: isOpen ?? false, setIsOpen }), [isOpen, setIsOpen]);
  return (
    <ChainOfThoughtContext.Provider value={ctx}>
      <div className={cn("not-prose max-w-prose space-y-4", className)} {...props}>{children}</div>
    </ChainOfThoughtContext.Provider>
  );
});

export const ChainOfThoughtHeader = memo(({ className, children, ...props }: ComponentProps<typeof CollapsibleTrigger>) => {
  const { isOpen, setIsOpen } = useChainOfThought();
  return (
    <Collapsible onOpenChange={setIsOpen} open={isOpen}>
      <CollapsibleTrigger className={cn("flex w-full items-center gap-2 text-muted-foreground text-sm transition-colors hover:text-foreground", className)} {...props}>
        <BrainIcon className="size-4" />
        <span className="flex-1 text-left">{children ?? "Chain of Thought"}</span>
        <ChevronDownIcon className={cn("size-4 transition-transform", isOpen ? "rotate-180" : "rotate-0")} />
      </CollapsibleTrigger>
    </Collapsible>
  );
});

export type ChainOfThoughtStepProps = ComponentProps<"div"> & {
  icon?: LucideIcon;
  label: ReactNode;
  description?: ReactNode;
  status?: "complete" | "active" | "pending";
};

export const ChainOfThoughtStep = memo(({ className, icon: Icon = DotIcon, label, description, status = "complete", children, ...props }: ChainOfThoughtStepProps) => {
  const statusStyles = { complete: "text-muted-foreground", active: "text-foreground", pending: "text-muted-foreground/50" };
  return (
    <div className={cn("flex gap-2 text-sm", statusStyles[status], "fade-in-0 slide-in-from-top-2 animate-in", className)} {...props}>
      <div className="relative mt-0.5"><Icon className="size-4" /><div className="-mx-px absolute top-7 bottom-0 left-1/2 w-px bg-border" /></div>
      <div className="flex-1 space-y-2 overflow-hidden">
        <div>{label}</div>
        {description && <div className="text-muted-foreground text-xs">{description}</div>}
        {children}
      </div>
    </div>
  );
});

export const ChainOfThoughtSearchResults = memo(({ className, ...props }: ComponentProps<"div">) => (
  <div className={cn("flex flex-wrap items-center gap-2", className)} {...props} />
));

export const ChainOfThoughtSearchResult = memo(({ className, children, ...props }: ComponentProps<typeof Badge>) => (
  <Badge className={cn("gap-1 px-2 py-0.5 font-normal text-xs", className)} variant="secondary" {...props}>{children}</Badge>
));

export const ChainOfThoughtContent = memo(({ className, children, ...props }: ComponentProps<typeof CollapsibleContent>) => {
  const { isOpen } = useChainOfThought();
  return (
    <Collapsible open={isOpen}>
      <CollapsibleContent className={cn("mt-2 space-y-3", "data-[state=closed]:fade-out-0 data-[state=open]:slide-in-from-top-2 text-popover-foreground outline-none data-[state=closed]:animate-out data-[state=open]:animate-in", className)} {...props}>
        {children}
      </CollapsibleContent>
    </Collapsible>
  );
});
