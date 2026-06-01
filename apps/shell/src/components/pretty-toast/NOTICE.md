# Vendored: react-native-pretty-toast (web subset)

These files are copied from **react-native-pretty-toast** v1.0.1 (MIT license),
from `temp/react-native-pretty-toast-1.0.1/src`. Only the DOM/web-portable subset
is vendored — the React Native native components have no runtime on the Tauri
(Windows/DOM) target.

Used **only** for the transient card layer (info + approval cards): the FIFO
queue, `force`/`maxQueue`, auto-dismiss, swipe-up dismissal, and `aria-live`
announcements. The Dynamic Island morph pill is a separate component
(`../dynamic-island/`), derived from the smoothui island.

## Files & changes

| File | Origin | Change |
|------|--------|--------|
| `WebToastView.tsx` | `src/WebToastView.tsx` | verbatim |
| `ToastProvider.tsx` | `src/ToastProvider.web.tsx` | renamed (dropped `.web`); web implementation, no native code |
| `toast.ts`, `useToast.ts`, `variants.ts`, `index.tsx`, `sf-symbols-typescript.ts` | same names | verbatim |
| `types.ts` | `src/types.ts` | removed `import … from 'react-native'`; `ColorValue`/`ImageSourcePropType` aliased to web shapes |

**Not** vendored: `ToastProvider.tsx` (native), `ToastViewNativeComponent.ts`,
`ios/`, `android/`.

Upstream license: MIT. Retain this NOTICE when updating.
