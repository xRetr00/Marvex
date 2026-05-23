/**
 * Edge-triggered hover tracker. Calls `onChange` only when the over/not-over
 * state actually transitions, so a high-frequency mousemove stream produces at
 * most one call per enter/leave instead of one IPC call per pixel of motion.
 */
export function makeHoverEdgeTrigger(onChange: (over: boolean) => void) {
  let last: boolean | undefined;
  return (over: boolean) => {
    if (over === last) return;
    last = over;
    onChange(over);
  };
}
