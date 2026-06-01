import type { SFSymbols7_0 } from './sf-symbols-typescript';

// Vendored for Tauri/web: the upstream library imports these from 'react-native'.
// On the desktop (DOM) target there is no react-native runtime, so we alias them
// to the web-equivalent shapes `WebToastView`/`ToastProvider` actually consume.
type ColorValue = string;
type ImageSourcePropType = string | { uri?: string } | Array<{ uri?: string }>;

/**
 * Name of an [SF Symbol](https://developer.apple.com/sf-symbols/) to display
 * as the toast icon. Browse the full catalog in Apple's SF Symbols app or
 * online at https://sfsymbols.com.
 *
 * Common symbols are suggested via autocomplete; any SF Symbol name is
 * accepted. On Android the name is mapped to a bundled drawable via
 * substring matching (e.g. "checkmark" → check icon); on web, to a unicode
 * glyph.
 *
 * @example "checkmark.seal.fill"
 */
export type SFSymbolName = SFSymbols7_0 | (string & Record<never, never>);

/**
 * Trailing action rendered inside the toast pill — visually similar to
 * sonner's "Undo" pattern. Tapping the button invokes `onPress` and
 * dismisses the toast.
 */
export interface ToastAction {
  /** Text shown inside the button. Keep short ("Undo", "Retry", "Open"). */
  label: string;
  /**
   * Called when the user taps the button. The toast auto-dismisses
   * immediately after — you don't need to call `toast.dismiss()` yourself.
   */
  onPress: () => void;
}

/**
 * Configuration for a single toast. All fields except `id` are optional,
 * but at minimum a `title` (or `message`) is expected for the pill to
 * have anything to render.
 */
export interface ToastConfig {
  /**
   * Stable identifier for the toast. Used by `toast.update(id, ...)` and
   * `toast.dismiss(id)`. When omitted, the provider generates one and
   * returns it from `toast.show(...)`.
   */
  id?: string;
  /**
   * SF Symbol name driving the icon on iOS (and the mapped drawable/glyph
   * on Android/web). Ignored when `iconSource` is set.
   *
   * @see SFSymbolName
   */
  icon?: SFSymbolName;
  /**
   * Custom image source rendered in place of the SF Symbol. Supports any
   * RN `ImageSourcePropType` — bundled assets via `require()`, remote
   * URLs, or file URIs. When provided, `icon` is ignored.
   *
   * Notes:
   * - iOS supports http(s) and file URIs.
   * - Android supports http(s), file:// and absolute filesystem paths.
   *   Resource-based URIs from bundled assets in prod Hermes builds may
   *   not resolve — use a file URI or remote URL in that case.
   * - Web renders the URI directly in an `<img>` tag.
   */
  iconSource?: ImageSourcePropType;
  /** Main title line — bold, single or multi-line as the pill grows. */
  title?: string;
  /**
   * Secondary message line rendered below the title. Pill height expands
   * to fit the content.
   */
  message?: string;
  /**
   * How long the toast stays visible, in milliseconds. Ignored when
   * `autoDismiss` is `false` or `duration <= 0`. Defaults to 3000.
   */
  duration?: number;
  /**
   * Whether the toast automatically dismisses after `duration`. Set to
   * `false` for persistent toasts (e.g. loading states) that should only
   * close via user swipe or `toast.dismiss()`. Defaults to `true`.
   */
  autoDismiss?: boolean;
  /**
   * Whether the toast can be dismissed by swiping it upward. Defaults to
   * `true`. Disable for critical messages the user must acknowledge.
   */
  enableSwipeDismiss?: boolean;
  /**
   * Overrides the accent color derived from the icon. Drives the icon
   * tint and the pill's accent stroke.
   */
  accentColor?: ColorValue;
  /**
   * Fixed stroke color for the pill outline. When set, overrides the
   * dynamic backdrop-sampled stroke with a static value. The caller owns
   * the alpha channel — pass `rgba(...)` if you want transparency.
   */
  strokeColor?: ColorValue;
  /**
   * Skip the backdrop luminance sampler that normally flips the outline
   * between accent and neutral as the toast moves over varying
   * backdrops. Useful for performance-sensitive contexts or when you
   * want a consistent look via `strokeColor`. Defaults to `false`.
   */
  disableBackdropSampling?: boolean;
  /**
   * Optional trailing button inside the pill. Tapping it calls the
   * action's `onPress` and dismisses the toast.
   *
   * @see ToastAction
   */
  action?: ToastAction;
  /**
   * Custom screen-reader announcement triggered when the toast appears
   * (via `AccessibilityInfo.announceForAccessibility` on native,
   * aria-live region on web). Defaults to `title + message`. Set to an
   * empty string to disable the announcement entirely.
   */
  accessibilityAnnouncement?: string;
  /**
   * Called when the user taps the toast pill (not the action button).
   * The toast auto-dismisses immediately after if this handler is set.
   */
  onPress?: () => void;
  /**
   * Called once, synchronously, when the toast begins presenting. Fires
   * after queue selection but before the native expand animation starts.
   */
  onShow?: () => void;
  /**
   * Called once when the toast finishes dismissing, regardless of
   * reason (auto, swipe, tap, `toast.dismiss()`, superseded by `force`).
   * Use this for cleanup tied to the pill's lifetime.
   */
  onHide?: () => void;
  /**
   * Called *only* when the toast dismissed itself because its duration
   * timer elapsed. Not called for user-initiated dismissals. Fires
   * before `onHide`.
   *
   * Note: on native, a swipe-dismissal after `duration` has elapsed may
   * still be reported as auto-dismiss since JS cannot distnguish it
   * from the timer without a dedicated native event.
   */
  onAutoDismiss?: () => void;
}

/**
 * Per-call options that control *how* a toast is scheduled, independent
 * of its content. Passed as the second argument to `toast.show(cfg, opts)`.
 */
export interface ShowOptions {
  /**
   * Present this toast immediately, dismissing the currently visible one
   * and skipping normal queueing. Useful for critical interrupts like
   * session-expiry notifications that shouldn't wait behind unrelated
   * toasts.
   */
  force?: boolean;
}

/**
 * Messages passed to `toast.promise(...)`. Each field may be either a
 * plain string (rendered as the title) or a full `ToastConfig` (minus
 * `id`) for finer control over the toast in that state.
 *
 * The `success` and `error` variants additionally accept a function
 * receiving the resolved value / thrown error — handy for interpolating
 * runtime data into the message.
 *
 * @typeParam T - The value type the promise resolves to.
 */
export type PromiseMessages<T> = {
  /** Shown while the promise is pending. `autoDismiss` defaults to false here. */
  loading: string | Omit<ToastConfig, 'id'>;
  /** Shown when the promise resolves. Receives the resolved value. */
  success: string | ((value: T) => string | Omit<ToastConfig, 'id'>);
  /** Shown when the promise rejects. Receives the thrown error. */
  error: string | ((error: unknown) => string | Omit<ToastConfig, 'id'>);
};

/**
 * Imperative toast API exposed by `useToast()` and by the module-level
 * `toast` singleton. All methods are safe to call from outside the React
 * tree (e.g. API clients, redux middleware, non-component helpers).
 */
export interface ToastRef {
  /**
   * Show a toast. Returns the toast's id so it can be updated or
   * dismissed later. If called before `<ToastProvider>` has mounted,
   * the call is a no-op (warning logged in dev).
   */
  show: (config: ToastConfig, options?: ShowOptions) => string;
  /**
   * Shorthand for a success toast with a green check icon. Equivalent
   * to `show({ icon: 'checkmark.circle.fill', title, ...config })`.
   */
  success: (
    title: string,
    config?: Omit<ToastConfig, 'title'>,
    options?: ShowOptions
  ) => string;
  /** Shorthand for an error toast with a red X icon. */
  error: (
    title: string,
    config?: Omit<ToastConfig, 'title'>,
    options?: ShowOptions
  ) => string;
  /** Shorthand for an info toast with a blue "i" icon. */
  info: (
    title: string,
    config?: Omit<ToastConfig, 'title'>,
    options?: ShowOptions
  ) => string;
  /** Shorthand for a warning toast with an orange triangle icon. */
  warning: (
    title: string,
    config?: Omit<ToastConfig, 'title'>,
    options?: ShowOptions
  ) => string;
  /**
   * Shorthand for a loading toast with a spinner icon. `autoDismiss`
   * defaults to `false` so the toast stays until the caller explicitly
   * dismisses or updates it.
   */
  loading: (
    title: string,
    config?: Omit<ToastConfig, 'title'>,
    options?: ShowOptions
  ) => string;
  /**
   * Mutate an existing toast in place. Updates propagate to the live
   * view without re-running the enter animation. If the toast with the
   * given id is still queued (not yet visible), its config is patched
   * ahead of presentation.
   */
  update: (id: string, partial: Partial<Omit<ToastConfig, 'id'>>) => void;
  /**
   * Tie a toast's lifecycle to a promise: shows a loading toast, morphs
   * to the success or error content when the promise settles. Returns
   * the original promise so `await` chains are preserved.
   *
   * @example
   * toast.promise(api.save(), {
   *   loading: 'Saving…',
   *   success: 'Saved',
   *   error: (e) => `Failed: ${e.message}`,
   * });
   */
  promise: <T>(promise: Promise<T>, messages: PromiseMessages<T>) => Promise<T>;
  /**
   * Dismiss the toast with the given id, or the currently visible one
   * if no id is passed. If the id refers to a queued-but-not-visible
   * toast, it's simply removed from the queue.
   */
  dismiss: (id?: string) => void;
  /** Dismiss the visible toast and clear the pending queue. */
  dismissAll: () => void;
}

/**
 * Defaults merged into every toast config at the provider level.
 * Per-toast values passed to `toast.show(...)` always win.
 *
 * Content-specific fields (`id`, `title`, `message`, `icon`,
 * `iconSource`, `onPress`, `action`) are intentionally excluded — those
 * belong to individual toasts, not the provider default.
 */
export interface ToastProviderDefaults extends Omit<
  ToastConfig,
  'id' | 'title' | 'message' | 'icon' | 'iconSource' | 'onPress' | 'action'
> {}
