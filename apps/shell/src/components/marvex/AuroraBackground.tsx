/**
 * Subtle animated "aurora" backdrop — warm cream/tan blobs drifting over the
 * near-black base. Fixed, pointer-transparent, behind all content (z-0). Pure
 * CSS (radial gradients + transforms), respects prefers-reduced-motion.
 */
const BLOBS: Array<{ style: React.CSSProperties }> = [
  {
    style: {
      top: "-18%",
      left: "-10%",
      width: "60vw",
      height: "60vw",
      background: "radial-gradient(circle at center, rgba(255,224,194,0.20), transparent 65%)",
      opacity: 0.9,
      animation: "marvex-aurora-a 22s ease-in-out infinite",
    },
  },
  {
    style: {
      top: "10%",
      right: "-15%",
      width: "55vw",
      height: "55vw",
      background: "radial-gradient(circle at center, rgba(120,90,70,0.22), transparent 65%)",
      opacity: 0.8,
      animation: "marvex-aurora-b 27s ease-in-out infinite",
    },
  },
  {
    style: {
      bottom: "-25%",
      left: "20%",
      width: "65vw",
      height: "65vw",
      background: "radial-gradient(circle at center, rgba(66,56,46,0.30), transparent 60%)",
      opacity: 0.85,
      animation: "marvex-aurora-c 31s ease-in-out infinite",
    },
  },
];

export function AuroraBackground() {
  return (
    <div className="marvex-aurora" aria-hidden>
      {BLOBS.map((blob, i) => (
        <div key={i} className="marvex-aurora__blob" style={blob.style} />
      ))}
      {/* faint vignette so edges stay grounded */}
      <div style={{ position: "absolute", inset: 0, background: "radial-gradient(120% 90% at 50% 0%, transparent 55%, rgba(0,0,0,0.45))" }} />
    </div>
  );
}

export default AuroraBackground;
