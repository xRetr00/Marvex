export type IslandCardKind = "info" | "result" | "agenda" | "approval";

export type IslandCard = {
  id: string;
  kind: IslandCardKind;
  title?: string;
  body?: string;
  duration?: number;
  autoDismiss?: boolean;
  actionLabel?: string;
  onAction?: () => void | Promise<void>;
  payload?: unknown;
};

export type IslandQueueSnapshot = {
  active: IslandCard | null;
  queued: IslandCard[];
};

export type IslandQueueOptions = {
  maxQueue?: number;
  onChange?: (snapshot: IslandQueueSnapshot) => void;
};

export type IslandShowOptions = {
  force?: boolean;
};

export function createIslandQueue(options: IslandQueueOptions = {}) {
  let active: IslandCard | null = null;
  let queued: IslandCard[] = [];
  let timer: ReturnType<typeof setTimeout> | null = null;

  const snapshot = (): IslandQueueSnapshot => ({ active, queued: [...queued] });

  const emit = () => options.onChange?.(snapshot());

  const clearTimer = () => {
    if (timer) clearTimeout(timer);
    timer = null;
  };

  const trimQueue = () => {
    if (typeof options.maxQueue !== "number" || options.maxQueue < 0) return;
    while (queued.length > options.maxQueue) queued.shift();
  };

  const armTimer = () => {
    clearTimer();
    if (!active) return;
    const autoDismiss = active.autoDismiss ?? true;
    const duration = active.duration ?? 5000;
    if (!autoDismiss || duration <= 0) return;
    timer = setTimeout(() => {
      dismiss(active?.id);
    }, duration);
  };

  const promote = () => {
    active = queued.shift() ?? null;
    armTimer();
    emit();
  };

  const show = (card: IslandCard, showOptions: IslandShowOptions = {}) => {
    if (showOptions.force) {
      active = card;
      trimQueue();
      armTimer();
      emit();
      return card.id;
    }
    if (!active) {
      active = card;
      armTimer();
      emit();
      return card.id;
    }
    queued.push(card);
    trimQueue();
    emit();
    return card.id;
  };

  const update = (id: string, partial: Partial<Omit<IslandCard, "id">>) => {
    if (active?.id === id) {
      active = { ...active, ...partial, id };
      armTimer();
      emit();
      return;
    }
    queued = queued.map((card) => (card.id === id ? { ...card, ...partial, id } : card));
    emit();
  };

  const dismiss = (id?: string) => {
    if (id && active?.id !== id) {
      queued = queued.filter((card) => card.id !== id);
      emit();
      return;
    }
    clearTimer();
    promote();
  };

  const dismissAll = () => {
    clearTimer();
    active = null;
    queued = [];
    emit();
  };

  return { show, update, dismiss, dismissAll, snapshot };
}
