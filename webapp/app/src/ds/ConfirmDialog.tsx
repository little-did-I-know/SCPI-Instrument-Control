import React, { useCallback, useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { Button, type ButtonVariant } from "./Button";

export type ConfirmDialogProps = {
  title: string;
  body: React.ReactNode;
  confirmLabel: string;
  variant?: ButtonVariant;
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
};

const FOCUSABLE = "button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex='-1'])";

/**
 * ConfirmDialog — a modal confirmation for a destructive action.
 *
 * Portalled to document.body rather than rendered in place: both call sites sit
 * inside a GroupBox fieldset, and an in-flow dialog can land below the fold on a
 * long list, so the operator clicks a destructive button and sees nothing happen.
 *
 * Hand-rolled rather than a native <dialog>: this project tests components under
 * jsdom, which has no showModal(), so a native dialog would make every test
 * exercise a polyfill instead of the component.
 */
export function ConfirmDialog({ title, body, confirmLabel, variant = "danger", busy = false, onConfirm, onCancel }: ConfirmDialogProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  const openerRef = useRef<HTMLElement | null>(null);

  // Focus lands on Cancel, and returns to the opener on unmount -- without the
  // latter a keyboard user is dropped back at the top of the document.
  useEffect(() => {
    openerRef.current = document.activeElement as HTMLElement | null;
    panelRef.current?.querySelector<HTMLElement>("[data-confirm-cancel]")?.focus();
    return () => openerRef.current?.focus?.();
  }, []);

  const dismiss = useCallback(() => {
    if (!busy) onCancel();
  }, [busy, onCancel]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        dismiss();
        return;
      }
      if (event.key !== "Tab") return;
      const panel = panelRef.current;
      if (!panel) return;
      const focusable = Array.from(panel.querySelectorAll<HTMLElement>(FOCUSABLE));
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [dismiss]);

  return createPortal(
    <div
      data-testid="confirm-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) dismiss();
      }}
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0, 0, 0, 0.45)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "var(--space-4)",
        zIndex: 1000,
      }}
    >
      <div
        role="alertdialog"
        aria-modal="true"
        aria-label={title}
        ref={panelRef}
        style={{
          border: "1px solid var(--lc-border-strong)",
          borderRadius: "var(--lc-radius)",
          background: "var(--lc-panel)",
          boxShadow: "var(--lc-elev-1)",
          padding: "var(--space-3)",
          display: "flex",
          flexDirection: "column",
          gap: "var(--space-2)",
          maxWidth: "360px",
        }}
      >
        <strong style={{ fontFamily: "var(--font-ui)", fontSize: "var(--text-sm)" }}>{title}</strong>
        <div style={{ fontFamily: "var(--font-ui)" }}>{body}</div>
        <div style={{ display: "flex", gap: "var(--space-2)", justifyContent: "flex-end" }}>
          <Button data-confirm-cancel="" disabled={busy} onClick={dismiss}>
            Cancel
          </Button>
          <Button variant={variant} disabled={busy} onClick={onConfirm}>
            {confirmLabel}
          </Button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
