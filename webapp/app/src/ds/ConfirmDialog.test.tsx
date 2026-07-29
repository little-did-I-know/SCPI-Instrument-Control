import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ConfirmDialog } from "./ConfirmDialog";

function setup(overrides: Partial<React.ComponentProps<typeof ConfirmDialog>> = {}) {
  const onConfirm = vi.fn();
  const onCancel = vi.fn();
  render(<ConfirmDialog title="Close bench?" body="This ends the session." confirmLabel="Close" onConfirm={onConfirm} onCancel={onCancel} {...overrides} />);
  return { onConfirm, onCancel };
}

describe("ConfirmDialog", () => {
  it("names itself and renders its body and actions", () => {
    setup();
    const dialog = screen.getByRole("alertdialog", { name: "Close bench?" });
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(screen.getByText("This ends the session.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Close" })).toBeInTheDocument();
  });

  it("focuses Cancel, not the confirming action", () => {
    // A destructive confirmation should treat a stray Enter as "cancel".
    setup();
    expect(screen.getByRole("button", { name: "Cancel" })).toHaveFocus();
  });

  it("cancels on Escape", async () => {
    const { onCancel } = setup();
    await userEvent.keyboard("{Escape}");
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it("cancels on a backdrop click", async () => {
    const { onCancel } = setup();
    await userEvent.click(screen.getByTestId("confirm-backdrop"));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it("does not cancel on a click inside the panel", async () => {
    const { onCancel } = setup();
    await userEvent.click(screen.getByText("This ends the session."));
    expect(onCancel).not.toHaveBeenCalled();
  });

  it("ignores Escape and backdrop clicks while busy", async () => {
    // A half-dismissed dialog during a slow close would leave the operator
    // unsure whether the action went through.
    const { onCancel } = setup({ busy: true });
    await userEvent.keyboard("{Escape}");
    await userEvent.click(screen.getByTestId("confirm-backdrop"));
    expect(onCancel).not.toHaveBeenCalled();
  });

  it("confirms when the confirming action is pressed", async () => {
    const { onConfirm } = setup();
    await userEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it("keeps Tab inside the dialog", async () => {
    setup();
    const cancel = screen.getByRole("button", { name: "Cancel" });
    const confirm = screen.getByRole("button", { name: "Close" });
    expect(cancel).toHaveFocus();
    await userEvent.tab();
    expect(confirm).toHaveFocus();
    await userEvent.tab();
    expect(cancel).toHaveFocus();
    await userEvent.tab({ shift: true });
    expect(confirm).toHaveFocus();
  });

  it("keeps Tab inside the dialog while busy, even though both buttons are disabled", async () => {
    // Both buttons are disabled while busy, so the focusable-elements query
    // that the trap relies on comes back empty. Without a fallback, Tab is
    // never preventDefault-ed and escapes straight to the page behind the
    // backdrop -- exactly the state a slow Close or Revoke sits in.
    setup({ busy: true });
    const dialog = screen.getByRole("alertdialog");
    await userEvent.tab();
    expect(dialog.contains(document.activeElement)).toBe(true);
    await userEvent.tab();
    expect(dialog.contains(document.activeElement)).toBe(true);
  });

  it("re-traps Tab after a click inside the panel blurs focus off the end buttons", async () => {
    // Clicking the dialog's non-focusable body text can blur focus away
    // from Cancel/Close, landing document.activeElement somewhere that
    // matches neither "at first, shift+Tab" nor "at last, Tab" -- so
    // without a contained-in-panel check, Tab falls through to native
    // order and can land on a focusable element on the page behind the
    // dialog (here, one that renders earlier in the document).
    render(
      <>
        <button>Other row action</button>
        <ConfirmDialog title="Close bench?" body="This ends the session." confirmLabel="Close" onConfirm={vi.fn()} onCancel={vi.fn()} />
      </>,
    );
    const other = screen.getByRole("button", { name: "Other row action" });
    await userEvent.click(screen.getByText("This ends the session."));

    const dialog = screen.getByRole("alertdialog");
    await userEvent.tab();
    expect(dialog.contains(document.activeElement)).toBe(true);
    expect(other).not.toHaveFocus();
  });

  it("wires the accessible name and description so a screen reader announces the consequence", () => {
    setup();
    const dialog = screen.getByRole("alertdialog");
    const labelledBy = dialog.getAttribute("aria-labelledby");
    const describedBy = dialog.getAttribute("aria-describedby");
    expect(labelledBy).toBeTruthy();
    expect(describedBy).toBeTruthy();
    expect(document.getElementById(labelledBy as string)).toHaveTextContent("Close bench?");
    expect(document.getElementById(describedBy as string)).toHaveTextContent("This ends the session.");
  });

  it("renders a passed-in error inside the panel, as an alert", () => {
    setup({ error: "session already closing" });
    const dialog = screen.getByRole("alertdialog");
    expect(within(dialog).getByRole("alert")).toHaveTextContent("session already closing");
  });

  it("returns focus to whatever opened it", async () => {
    function Harness() {
      const [open, setOpen] = useState(false);
      return (
        <>
          <button onClick={() => setOpen(true)}>Open</button>
          {open ? <ConfirmDialog title="Close bench?" body="body" confirmLabel="Close" onConfirm={() => setOpen(false)} onCancel={() => setOpen(false)} /> : null}
        </>
      );
    }
    render(<Harness />);
    const opener = screen.getByRole("button", { name: "Open" });
    await userEvent.click(opener);
    await userEvent.keyboard("{Escape}");
    expect(opener).toHaveFocus();
  });
});
