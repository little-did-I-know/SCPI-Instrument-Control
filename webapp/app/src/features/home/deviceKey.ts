import type { DiscoveredDevice } from "../../api/types";

/**
 * Stable identity for a device across React keys and busy tracking.
 * A held session is identified by its session_id (so two mock sessions —
 * both address-less, same model — stay distinct); a free device by its
 * address; and anything else falls back to the model.
 */
export function deviceKey(device: Pick<DiscoveredDevice, "session_id" | "address" | "model">): string {
  return device.session_id ?? device.address ?? device.model;
}
