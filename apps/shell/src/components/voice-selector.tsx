import { useControllableState } from "@radix-ui/react-use-controllable-state";
import { CircleIcon, LoaderCircleIcon, MarsIcon, PauseIcon, PlayIcon, VenusIcon } from "lucide-react";
import type { ComponentProps, ReactNode } from "react";
import { createContext, useContext, useMemo } from "react";
import { Button } from "@/components/ui/button";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList, CommandSeparator, CommandShortcut } from "@/components/ui/command";
import { Dialog, DialogContent, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

interface VoiceSelectorContextValue {
  value: string | undefined;
  setValue: (value: string | undefined) => void;
  open: boolean;
  setOpen: (open: boolean) => void;
}

const VoiceSelectorContext = createContext<VoiceSelectorContextValue | null>(null);

export const useVoiceSelector = () => {
  const ctx = useContext(VoiceSelectorContext);
  if (!ctx) throw new Error("VoiceSelector components must be used within VoiceSelector");
  return ctx;
};

export type VoiceSelectorProps = ComponentProps<typeof Dialog> & {
  value?: string;
  defaultValue?: string;
  onValueChange?: (value: string | undefined) => void;
};

export const VoiceSelector = ({ value: valueProp, defaultValue, onValueChange, open: openProp, defaultOpen = false, onOpenChange, children, ...props }: VoiceSelectorProps) => {
  const [value, setValue] = useControllableState({ prop: valueProp, defaultProp: defaultValue, onChange: onValueChange });
  const [open, setOpen] = useControllableState({ prop: openProp, defaultProp: defaultOpen, onChange: onOpenChange });
  const ctx = useMemo(() => ({ value, setValue, open: open ?? false, setOpen }), [value, setValue, open, setOpen]);
  return (
    <VoiceSelectorContext.Provider value={ctx}>
      <Dialog onOpenChange={setOpen} open={open} {...props}>{children}</Dialog>
    </VoiceSelectorContext.Provider>
  );
};

export const VoiceSelectorTrigger = (props: ComponentProps<typeof DialogTrigger>) => <DialogTrigger {...props} />;

export const VoiceSelectorContent = ({ className, children, title = "Voice Selector", ...props }: ComponentProps<typeof DialogContent> & { title?: ReactNode }) => (
  <DialogContent className={cn("p-0", className)} {...props}>
    <DialogTitle className="sr-only">{title}</DialogTitle>
    <Command>{children}</Command>
  </DialogContent>
);

export const VoiceSelectorInput = ({ className, ...props }: ComponentProps<typeof CommandInput>) => (
  <CommandInput className={cn("h-auto py-3.5", className)} {...props} />
);

export const VoiceSelectorList = (props: ComponentProps<typeof CommandList>) => <CommandList {...props} />;
export const VoiceSelectorEmpty = (props: ComponentProps<typeof CommandEmpty>) => <CommandEmpty {...props} />;
export const VoiceSelectorGroup = (props: ComponentProps<typeof CommandGroup>) => <CommandGroup {...props} />;
export const VoiceSelectorItem = ({ className, ...props }: ComponentProps<typeof CommandItem>) => <CommandItem className={cn("px-4 py-2", className)} {...props} />;
export const VoiceSelectorShortcut = (props: ComponentProps<typeof CommandShortcut>) => <CommandShortcut {...props} />;
export const VoiceSelectorSeparator = (props: ComponentProps<typeof CommandSeparator>) => <CommandSeparator {...props} />;

export const VoiceSelectorGender = ({ className, value, children, ...props }: ComponentProps<"span"> & { value?: "male" | "female" | "transgender" | "androgyne" | "non-binary" | "intersex" }) => {
  let icon: ReactNode | null = null;
  switch (value) {
    case "male": icon = <MarsIcon className="size-4" />; break;
    case "female": icon = <VenusIcon className="size-4" />; break;
    default: icon = <CircleIcon className="size-4" />;
  }
  return <span className={cn("text-muted-foreground text-xs", className)} {...props}>{children ?? icon}</span>;
};

const accentEmojis: Record<string, string> = {
  american: "🇺🇸", british: "🇬🇧", australian: "🇦🇺", canadian: "🇨🇦",
  irish: "🇮🇪", indian: "🇮🇳", french: "🇫🇷", german: "🇩🇪",
  italian: "🇮🇹", spanish: "🇪🇸", japanese: "🇯🇵", chinese: "🇨🇳", korean: "🇰🇷",
};

export const VoiceSelectorAccent = ({ className, value, children, ...props }: ComponentProps<"span"> & { value?: string }) => {
  const emoji = value ? accentEmojis[value] : null;
  return <span className={cn("text-muted-foreground text-xs", className)} {...props}>{children ?? emoji}</span>;
};

export const VoiceSelectorName = ({ className, ...props }: ComponentProps<"span">) => (
  <span className={cn("flex-1 truncate text-left font-medium", className)} {...props} />
);

export const VoiceSelectorDescription = ({ className, ...props }: ComponentProps<"span">) => (
  <span className={cn("text-muted-foreground text-xs", className)} {...props} />
);

export const VoiceSelectorAttributes = ({ className, children, ...props }: ComponentProps<"div">) => (
  <div className={cn("flex items-center text-xs", className)} {...props}>{children}</div>
);

export const VoiceSelectorBullet = ({ className, ...props }: ComponentProps<"span">) => (
  <span aria-hidden="true" className={cn("select-none text-border", className)} {...props}>&bull;</span>
);

export const VoiceSelectorPreview = ({ className, playing, loading, onPlay, onClick, ...props }: Omit<ComponentProps<"button">, "children"> & { playing?: boolean; loading?: boolean; onPlay?: () => void }) => {
  const handleClick = (event: React.MouseEvent<HTMLButtonElement>) => { event.stopPropagation(); onClick?.(event); onPlay?.(); };
  let icon = <PlayIcon className="size-3" />;
  if (loading) icon = <LoaderCircleIcon className="size-3 animate-spin" />;
  else if (playing) icon = <PauseIcon className="size-3" />;
  return (
    <Button aria-label={playing ? "Pause preview" : "Play preview"} className={cn("size-6", className)} disabled={loading} onClick={handleClick} size="icon" type="button" variant="outline" {...props}>
      {icon}
    </Button>
  );
};
