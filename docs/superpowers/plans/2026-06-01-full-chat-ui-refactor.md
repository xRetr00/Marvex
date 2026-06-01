# Full Chat UI Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the Marvex shell chat, history, settings, status/logs, and voice surfaces into a polished Assistant OS UI while preserving Marvex turn/session contracts.

**Architecture:** Keep runtime ownership in `apps/shell/src/surfaces/ChatApp.tsx` and render with shell-native components. Add focused presentation primitives under `apps/shell/src/components/chatbot-main` and `apps/shell/src/components/marvex`, adapting useful Agent Elements patterns without converting Marvex to `UIMessage`.

**Tech Stack:** React 19, Vite, Tailwind v4, existing shadcn-style UI primitives, lucide icons, existing shell API clients.

---

### Task 1: Chat Message Behavior And Markdown

**Files:**
- Create: `apps/shell/src/components/chatbot-main/markdown.tsx`
- Create: `apps/shell/src/components/chatbot-main/activity.tsx`
- Modify: `apps/shell/src/components/marvex/RichMessage.tsx`
- Modify: `apps/shell/src/components/chatbot-main/MarvexChatShell.tsx`
- Modify: `apps/shell/src/surfaces/ChatApp.tsx`
- Test: `apps/shell/src/components/chatbot-main/MarvexChatShell.test.tsx`

- [ ] **Step 1: Write failing tests**

Add tests that assert markdown text renders as formatted content, approval IDs are not visible, approval decisions mutate the existing assistant message, and clarification answers call the update callback without adding a duplicate local visible answer.

- [ ] **Step 2: Run red test**

Run: `npm test -- MarvexChatShell.test.tsx`
Expected: FAIL because markdown, raw approval suppression, and in-place clarification status are not implemented.

- [ ] **Step 3: Implement markdown and activity primitives**

Implement a local markdown renderer that handles headings, lists, inline code, fenced code, links, tables, and evidence references. Implement shimmer/thinking UI and polished reasoning stage disclosure.

- [ ] **Step 4: Implement in-place chat behavior**

Update `ChatApp.tsx` so approval outcomes replace/sanitize the existing assistant content instead of concatenating raw approval prose, and clarification answers mark the existing question card as answered while sending the resolved backend turn.

- [ ] **Step 5: Run green test**

Run: `npm test -- MarvexChatShell.test.tsx`
Expected: PASS.

### Task 2: Prompt Composer And Header/Sidebar

**Files:**
- Modify: `apps/shell/src/components/chatbot-main/prompt-input.tsx`
- Modify: `apps/shell/src/surfaces/ChatApp.tsx`
- Test: `apps/shell/src/components/chatbot-main/MarvexChatShell.test.tsx`

- [ ] **Step 1: Write failing tests**

Assert the composer shows an agent-aware hint strip, character count, Send/Stop toggle during generation, and the header does not expose the local URL.

- [ ] **Step 2: Run red test**

Run: `npm test -- MarvexChatShell.test.tsx`
Expected: FAIL because the current composer lacks these elements.

- [ ] **Step 3: Implement composer/header/sidebar**

Add stop callback support, character count, hint strip, model/session context in the header, and a denser chat history rail with preview/update metadata and no token counts.

- [ ] **Step 4: Run green test**

Run: `npm test -- MarvexChatShell.test.tsx`
Expected: PASS.

### Task 3: Settings, Status/Logs, And Voice Visual Hierarchy

**Files:**
- Modify: `apps/shell/src/surfaces/ControlPlaneSettings.tsx`
- Modify: `apps/shell/src/components/marvex/StatusView.tsx`
- Modify: `apps/shell/src/components/marvex/LogsView.tsx`
- Modify: `apps/shell/src/surfaces/VoiceMode.tsx`
- Test: `apps/shell/src/surfaces/ControlPlaneSettings.test.tsx`
- Test: `apps/shell/src/components/marvex/LogsView.test.tsx`
- Test: `apps/shell/src/surfaces/VoiceMode.test.tsx`

- [ ] **Step 1: Write failing tests**

Assert the surfaces render accessible headings, provider/model card controls, visual status labels, and voice model asset cards.

- [ ] **Step 2: Run red tests**

Run: `npm test -- ControlPlaneSettings.test.tsx LogsView.test.tsx VoiceMode.test.tsx`
Expected: FAIL where old labels/cards are missing.

- [ ] **Step 3: Implement surface polish**

Replace native-looking rows with glass panels, icon cards, pill toggles, provider logos where possible, structured trace/log/status cards, and voice asset download cards.

- [ ] **Step 4: Run green tests**

Run: `npm test -- ControlPlaneSettings.test.tsx LogsView.test.tsx VoiceMode.test.tsx`
Expected: PASS.

### Task 4: Full Verification

**Files:**
- Run-only verification for shell package.

- [ ] **Step 1: Run focused tests**

Run: `npm test -- MarvexChatShell.test.tsx ControlPlaneSettings.test.tsx LogsView.test.tsx VoiceMode.test.tsx`
Expected: PASS.

- [ ] **Step 2: Run shell build**

Run: `npm run build`
Expected: PASS.

- [ ] **Step 3: Inspect diff**

Run: `git diff --stat` and `git diff --check`
Expected: no whitespace errors and only intended UI files changed.
