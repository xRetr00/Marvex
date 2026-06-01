import type { ToastConfig } from './types';

export type ToastVariant = 'success' | 'error' | 'info' | 'warning' | 'loading';

const VARIANT_ICONS: Record<ToastVariant, string> = {
  success: 'checkmark.circle.fill',
  error: 'xmark.circle.fill',
  info: 'info.circle.fill',
  warning: 'exclamationmark.triangle.fill',
  loading: 'arrow.triangle.2.circlepath',
};

export function variantConfig(
  variant: ToastVariant,
  title: string,
  extra?: Omit<ToastConfig, 'title'>
): ToastConfig {
  const icon = extra?.icon ?? VARIANT_ICONS[variant];
  const base: ToastConfig = { ...extra, title, icon };
  if (variant === 'loading' && base.autoDismiss === undefined) {
    base.autoDismiss = false;
  }
  return base;
}
