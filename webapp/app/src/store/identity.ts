import { create } from "zustand";

type IdentityStore = {
  identity: string | null;
  setIdentity: (identity: string) => void;
  clearIdentity: () => void;
};

/**
 * Who this browser is, as far as the gateway is concerned. TokenGate learns
 * this once per verified token (the `whoami` response is the token's name)
 * and stores it here so anything in the tree — e.g. OwnerBadge deciding
 * whether the current viewer owns a session — can read it without a prop
 * drilled all the way from the token check.
 */
export const useIdentity = create<IdentityStore>((set) => ({
  identity: null,
  setIdentity: (identity) => set({ identity }),
  clearIdentity: () => set({ identity: null }),
}));
