export interface InfoCardProps {
  title: string;
  body?: string;
  onDismiss?: () => void;
}

// Lightweight transient card (e.g. the welcome message) shown inside the expanded
// island. Auto-dismissal is handled by the queue; the button is an optional escape.
export function InfoCard({ title, body, onDismiss }: InfoCardProps) {
  return (
    <div role="status" aria-live="polite" style={rootStyle}>
      <span aria-hidden style={iconStyle}>M</span>
      <div style={{ minWidth: 0, flex: 1 }}>
        <div style={titleStyle}>{title}</div>
        {body ? <div style={bodyStyle}>{body}</div> : null}
      </div>
      {onDismiss ? (
        <button type="button" onClick={(e) => { e.stopPropagation(); onDismiss(); }} style={btnStyle}>
          Dismiss
        </button>
      ) : null}
    </div>
  );
}

const rootStyle: React.CSSProperties = { display: "flex", alignItems: "center", gap: 10, width: "100%" };
const iconStyle: React.CSSProperties = {
  width: 28, height: 28, flexShrink: 0, borderRadius: 999, display: "grid", placeItems: "center",
  background: "rgba(255,224,194,0.10)", boxShadow: "inset 0 0 0 1px rgba(255,224,194,0.18)",
  color: "#ffe0c2", fontWeight: 800, fontSize: 14,
};
const titleStyle: React.CSSProperties = { fontSize: 13, fontWeight: 650, letterSpacing: "-0.01em", color: "#fff" };
const bodyStyle: React.CSSProperties = { marginTop: 2, fontSize: 11.5, lineHeight: "15px", color: "rgba(255,255,255,0.6)", overflowWrap: "anywhere" };
const btnStyle: React.CSSProperties = {
  border: 0, borderRadius: 999, padding: "5px 11px", fontSize: 11, fontWeight: 650, cursor: "pointer",
  background: "rgba(255,255,255,0.09)", boxShadow: "inset 0 0 0 1px rgba(255,255,255,0.10)", color: "#ffe0c2",
  whiteSpace: "nowrap", flexShrink: 0,
};
