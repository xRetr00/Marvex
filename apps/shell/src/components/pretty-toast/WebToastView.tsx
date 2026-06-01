/* eslint-disable react-native/no-inline-styles */
import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import type { PointerEvent as ReactPointerEvent } from 'react';
import { createPortal } from 'react-dom';
import type { SFSymbolName } from './types';

export interface WebToastViewProps {
  visible: boolean;
  icon?: SFSymbolName;
  iconUri?: string;
  title?: string;
  message?: string;
  duration?: number;
  autoDismiss?: boolean;
  enableSwipeDismiss?: boolean;
  useDynamicIsland?: boolean;
  accentColor?: string;
  strokeColor?: string;
  disableBackdropSampling?: boolean;
  actionLabel?: string;
  onToastDismiss?: () => void;
  onToastPress?: () => void;
  onToastActionPress?: () => void;
}

type IconInfo = { glyph: string | null; color: string };

const ICON_MAP: Array<[string, IconInfo]> = [
  ['checkmark', { glyph: '✓', color: '#30D158' }],
  ['xmark', { glyph: '✕', color: '#FF453A' }],
  ['info', { glyph: 'ℹ', color: '#0A84FF' }],
  ['exclamation', { glyph: '!', color: '#FF9F0A' }],
  ['heart', { glyph: '♥', color: '#FF375F' }],
  ['arrow.up', { glyph: '↑', color: '#0A84FF' }],
  ['arrow.down', { glyph: '↓', color: '#0A84FF' }],
  ['envelope', { glyph: '✉', color: '#FFFFFF' }],
];

function getIcon(symbol: string): IconInfo {
  for (const [key, value] of ICON_MAP) {
    if (symbol.includes(key)) return value;
  }
  return { glyph: null, color: '#FFFFFF' };
}

const ENTER_MS = 450;
const EXIT_MS = 350;
const ENTER_EASING = 'cubic-bezier(0.22, 1.2, 0.36, 1)';
const EXIT_EASING = 'cubic-bezier(0.4, 0, 0.2, 1)';
const SWIPE_THRESHOLD = -40;

export default function WebToastView({
  visible,
  icon = '',
  iconUri,
  title = '',
  message = '',
  duration = 3000,
  autoDismiss = true,
  enableSwipeDismiss = true,
  accentColor,
  strokeColor,
  disableBackdropSampling = false,
  actionLabel,
  onToastDismiss,
  onToastPress,
  onToastActionPress,
}: WebToastViewProps) {
  const [mounted, setMounted] = useState(false);
  const [entered, setEntered] = useState(false);
  const [dismissing, setDismissing] = useState(false);
  const [dragY, setDragY] = useState(0);
  const [isDragging, setIsDragging] = useState(false);
  const [isDark, setIsDark] = useState(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return false;
    return window.matchMedia('(prefers-color-scheme: dark)').matches;
  });

  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return;
    const mql = window.matchMedia('(prefers-color-scheme: dark)');
    const onChange = (e: MediaQueryListEvent) => setIsDark(e.matches);
    mql.addEventListener('change', onChange);
    return () => mql.removeEventListener('change', onChange);
  }, []);
  const dragStartYRef = useRef<number | null>(null);
  const lastDragYRef = useRef(0);
  const autoDismissTimerRef = useRef<ReturnType<typeof setTimeout> | null>(
    null
  );
  const exitTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clearAutoDismiss = () => {
    if (autoDismissTimerRef.current) {
      clearTimeout(autoDismissTimerRef.current);
      autoDismissTimerRef.current = null;
    }
  };

  const clearExit = () => {
    if (exitTimerRef.current) {
      clearTimeout(exitTimerRef.current);
      exitTimerRef.current = null;
    }
  };

  useEffect(() => {
    if (!visible) return;
    clearExit();
    clearAutoDismiss();
    setMounted(true);
    setEntered(false);
    setDismissing(false);
    setDragY(0);
    setIsDragging(false);
  }, [visible]);

  // Delay onToastDismiss until the exit transition finishes so queued
  // toasts don't interrupt the animation.
  useEffect(() => {
    const shouldExit = mounted && (!visible || dismissing);
    if (!shouldExit || exitTimerRef.current) return;
    setEntered(false);
    clearAutoDismiss();
    exitTimerRef.current = setTimeout(() => {
      exitTimerRef.current = null;
      setMounted(false);
      setDismissing(false);
      setDragY(0);
      onToastDismiss?.();
    }, EXIT_MS);
  }, [mounted, visible, dismissing, onToastDismiss]);

  useLayoutEffect(() => {
    if (!mounted || !visible || dismissing) return;
    const raf = requestAnimationFrame(() => setEntered(true));
    return () => cancelAnimationFrame(raf);
  }, [mounted, visible, dismissing]);

  useEffect(() => {
    if (!mounted || !visible || !entered || dismissing) return;
    clearAutoDismiss();
    if (autoDismiss && duration > 0) {
      autoDismissTimerRef.current = setTimeout(() => {
        setDismissing(true);
      }, duration);
    }
    return clearAutoDismiss;
  }, [mounted, visible, entered, dismissing, autoDismiss, duration]);

  useEffect(() => {
    return () => {
      clearAutoDismiss();
      clearExit();
    };
  }, []);

  if (typeof document === 'undefined' || !mounted) return null;

  const defaultIcon = getIcon(icon);
  const color = accentColor ?? defaultIcon.color;
  const glyph = defaultIcon.glyph;
  const outline = strokeColor
    ? strokeColor
    : disableBackdropSampling
      ? 'rgba(255,255,255,0.06)'
      : isDark
        ? `color-mix(in srgb, ${color} 20%, transparent)`
        : undefined;

  const isExiting = !visible || dismissing;

  let transform: string;
  let transition: string;
  if (isDragging) {
    transform = `translate(-50%, ${dragY}px) scale(1)`;
    transition = 'none';
  } else if (isExiting) {
    const exitY = dragY < 0 ? dragY - 40 : -20;
    transform = `translate(-50%, ${exitY}px) scale(1)`;
    transition = `transform ${EXIT_MS}ms ${EXIT_EASING}, opacity ${EXIT_MS}ms ${EXIT_EASING}`;
  } else if (entered) {
    transform = 'translate(-50%, 0) scale(1)';
    transition = `transform ${ENTER_MS}ms ${ENTER_EASING}, opacity ${ENTER_MS}ms ${ENTER_EASING}`;
  } else {
    transform = 'translate(-50%, -40px) scale(0.8)';
    transition = `transform ${ENTER_MS}ms ${ENTER_EASING}, opacity ${ENTER_MS}ms ${ENTER_EASING}`;
  }
  const opacity = isExiting ? 0 : entered ? 1 : 0;

  const handlePointerDown = (e: ReactPointerEvent<HTMLDivElement>) => {
    if (!enableSwipeDismiss || e.button !== 0) return;
    dragStartYRef.current = e.clientY;
    lastDragYRef.current = 0;
    e.currentTarget.setPointerCapture?.(e.pointerId);
  };

  const handlePointerMove = (e: ReactPointerEvent<HTMLDivElement>) => {
    if (dragStartYRef.current === null) return;
    const dy = Math.min(0, e.clientY - dragStartYRef.current);
    lastDragYRef.current = dy;
    if (!isDragging && dy < -2) setIsDragging(true);
    if (isDragging || dy < -2) setDragY(dy);
  };

  const handlePointerUp = (e: ReactPointerEvent<HTMLDivElement>) => {
    if (dragStartYRef.current === null) return;
    const dy = lastDragYRef.current;
    dragStartYRef.current = null;
    e.currentTarget.releasePointerCapture?.(e.pointerId);

    setIsDragging(false);

    if (dy < SWIPE_THRESHOLD) {
      // Don't reset dragY — the exit animates onward from here.
      setDismissing(true);
    } else {
      setDragY(0);
    }
  };

  const handleClick = () => {
    if (lastDragYRef.current < -4) return;
    if (onToastPress) onToastPress();
  };

  const pill = (
    <div
      role="status"
      aria-live="polite"
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      onPointerCancel={handlePointerUp}
      onClick={handleClick}
      style={{
        position: 'fixed',
        top: 16,
        left: '50%',
        transform,
        opacity,
        transition,
        zIndex: 2147483647,
        width: 'min(360px, calc(100vw - 20px))',
        boxSizing: 'border-box',
        background: '#000',
        border: outline ? `2px solid ${outline}` : 'none',
        borderRadius: 30,
        padding: '14px 20px',
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        fontFamily:
          '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
        userSelect: 'none',
        touchAction: 'none',
        cursor: onToastPress ? 'pointer' : 'default',
        boxShadow: '0 10px 30px rgba(0, 0, 0, 0.35)',
      }}
    >
      <div
        style={{
          width: 50,
          flexShrink: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: 35,
          lineHeight: 1,
          color,
        }}
      >
        {iconUri ? (
          <img
            src={iconUri}
            alt=""
            style={{ width: 40, height: 40, objectFit: 'contain' }}
          />
        ) : glyph ? (
          glyph
        ) : (
          <svg
            width="28"
            height="28"
            viewBox="0 0 24 24"
            fill="currentColor"
            style={{ display: 'block' }}
            aria-hidden="true"
          >
            <path d="M12 2.25a1 1 0 0 1 1 1v.6a7 7 0 0 1 6 6.93v3.36l1.38 2.07A1.25 1.25 0 0 1 19.34 18H4.66a1.25 1.25 0 0 1-1.04-1.94L5 14v-3.22a7 7 0 0 1 6-6.93v-.6a1 1 0 0 1 1-1Zm-2.5 17.25a2.5 2.5 0 0 0 5 0h-5Z" />
          </svg>
        )}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        {title ? (
          <div
            style={{
              color: '#fff',
              fontWeight: 600,
              fontSize: 15,
              lineHeight: '20px',
              wordBreak: 'break-word',
            }}
          >
            {title}
          </div>
        ) : null}
        {message ? (
          <div
            style={{
              color: 'rgba(255, 255, 255, 0.6)',
              fontSize: 12,
              lineHeight: '16px',
              marginTop: title ? 4 : 0,
              wordBreak: 'break-word',
            }}
          >
            {message}
          </div>
        ) : null}
      </div>
      {actionLabel && onToastActionPress ? (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onToastActionPress();
          }}
          onPointerDown={(e) => e.stopPropagation()}
          style={{
            flexShrink: 0,
            marginLeft: 4,
            padding: '6px 12px',
            background: 'rgba(255,255,255,0.12)',
            color: typeof color === 'string' ? color : '#fff',
            border: 'none',
            borderRadius: 999,
            fontSize: 13,
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >
          {actionLabel}
        </button>
      ) : null}
    </div>
  );

  return createPortal(pill, document.body);
}
