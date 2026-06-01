import type {
  PromiseMessages,
  ShowOptions,
  ToastConfig,
  ToastRef,
} from './types';

let activeRef: ToastRef | null = null;

export function _setActiveToastRef(ref: ToastRef | null): void {
  activeRef = ref;
}

declare const __DEV__: boolean | undefined;

function warnNoProvider(method: string): void {
  if (typeof __DEV__ === 'undefined' || __DEV__) {
    console.warn(
      `[react-native-pretty-toast] toast.${method}() called before <ToastProvider> mounted. Call was ignored.`
    );
  }
}

export const toast = {
  show(config: ToastConfig, options?: ShowOptions): string {
    if (!activeRef) {
      warnNoProvider('show');
      return '';
    }
    return activeRef.show(config, options);
  },
  success(
    title: string,
    config?: Omit<ToastConfig, 'title'>,
    options?: ShowOptions
  ): string {
    if (!activeRef) {
      warnNoProvider('success');
      return '';
    }
    return activeRef.success(title, config, options);
  },
  error(
    title: string,
    config?: Omit<ToastConfig, 'title'>,
    options?: ShowOptions
  ): string {
    if (!activeRef) {
      warnNoProvider('error');
      return '';
    }
    return activeRef.error(title, config, options);
  },
  info(
    title: string,
    config?: Omit<ToastConfig, 'title'>,
    options?: ShowOptions
  ): string {
    if (!activeRef) {
      warnNoProvider('info');
      return '';
    }
    return activeRef.info(title, config, options);
  },
  warning(
    title: string,
    config?: Omit<ToastConfig, 'title'>,
    options?: ShowOptions
  ): string {
    if (!activeRef) {
      warnNoProvider('warning');
      return '';
    }
    return activeRef.warning(title, config, options);
  },
  loading(
    title: string,
    config?: Omit<ToastConfig, 'title'>,
    options?: ShowOptions
  ): string {
    if (!activeRef) {
      warnNoProvider('loading');
      return '';
    }
    return activeRef.loading(title, config, options);
  },
  update(id: string, partial: Partial<Omit<ToastConfig, 'id'>>): void {
    if (!activeRef) {
      warnNoProvider('update');
      return;
    }
    activeRef.update(id, partial);
  },
  promise<T>(promise: Promise<T>, messages: PromiseMessages<T>): Promise<T> {
    if (!activeRef) {
      warnNoProvider('promise');
      return promise;
    }
    return activeRef.promise(promise, messages);
  },
  dismiss(id?: string): void {
    if (!activeRef) {
      warnNoProvider('dismiss');
      return;
    }
    activeRef.dismiss(id);
  },
  dismissAll(): void {
    if (!activeRef) {
      warnNoProvider('dismissAll');
      return;
    }
    activeRef.dismissAll();
  },
};
