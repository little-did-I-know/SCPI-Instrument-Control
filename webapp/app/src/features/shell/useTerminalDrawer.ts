import { create } from "zustand";

type TerminalDrawerStore = {
  open: boolean;
  toggle: () => void;
  close: () => void;
};

/** Open/closed state for the shell's SCPI console. A store rather than props
 *  because the toggle lives in the header (App.tsx) and the drawer lives in the
 *  shell, with the session view in between. */
export const useTerminalDrawer = create<TerminalDrawerStore>((set) => ({
  open: false,
  toggle: () => set((state) => ({ open: !state.open })),
  close: () => set({ open: false }),
}));
