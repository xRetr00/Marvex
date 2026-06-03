// Split an assistant message into its private reasoning ("thinking") and the
// user-facing answer. The model is instructed (see the prompt harness reasoning
// block) to wrap reasoning in a single <think>...</think> block and write the
// answer after the closing tag. This also tolerates the streaming case where the
// closing </think> has not arrived yet, so the UI can render live thinking.

const THINK_OPEN = "<think>";
const THINK_CLOSE = "</think>";

export interface ReasoningSplit {
  /** Private chain-of-thought, with the <think> tags removed. */
  thinking: string;
  /** User-facing answer (everything outside the think block). */
  answer: string;
  /** True while the think block is still open (reasoning is streaming in). */
  thinkingStreaming: boolean;
}

export function splitReasoning(text: string): ReasoningSplit {
  if (!text) {
    return { thinking: "", answer: "", thinkingStreaming: false };
  }
  if (text.indexOf(THINK_OPEN) === -1) {
    // No tagged reasoning. Models with a native reasoning channel surface it
    // elsewhere, so the whole text is the answer.
    return { thinking: "", answer: text, thinkingStreaming: false };
  }
  // Multi-tool turns can concatenate several <think> blocks across provider
  // calls. Collect every block as thinking and everything outside as the answer.
  const thinkingParts: string[] = [];
  const answerParts: string[] = [];
  let thinkingStreaming = false;
  let cursor = 0;
  while (cursor < text.length) {
    const openIdx = text.indexOf(THINK_OPEN, cursor);
    if (openIdx === -1) {
      answerParts.push(text.slice(cursor));
      break;
    }
    answerParts.push(text.slice(cursor, openIdx));
    const afterOpen = openIdx + THINK_OPEN.length;
    const closeIdx = text.indexOf(THINK_CLOSE, afterOpen);
    if (closeIdx === -1) {
      // Unterminated block: reasoning is still streaming in.
      thinkingParts.push(text.slice(afterOpen));
      thinkingStreaming = true;
      break;
    }
    thinkingParts.push(text.slice(afterOpen, closeIdx));
    cursor = closeIdx + THINK_CLOSE.length;
  }
  return {
    thinking: thinkingParts.join("\n").trim(),
    answer: answerParts.join("").trim(),
    thinkingStreaming,
  };
}

/** Strip reasoning so only the user-facing answer remains (speech, copy). */
export function stripReasoning(text: string): string {
  return splitReasoning(text).answer;
}
