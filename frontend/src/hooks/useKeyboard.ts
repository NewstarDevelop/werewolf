import { useEffect } from "react";

/**
 * Attach a document-level keydown listener, auto-ignoring when the user is
 * typing in a text input / textarea / contenteditable. Enabled only while
 * `enabled` is true (to avoid capturing keys when no pending action).
 */
export function useKeyboard(
  handler: (event: KeyboardEvent) => void,
  enabled: boolean,
): void {
  useEffect(() => {
    if (!enabled) return undefined;

    function onKey(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      const tag = target?.tagName;
      const isEditable =
        tag === "TEXTAREA"
        || tag === "INPUT"
        || target?.isContentEditable === true;
      if (isEditable) return;
      handler(event);
    }

    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [enabled, handler]);
}
