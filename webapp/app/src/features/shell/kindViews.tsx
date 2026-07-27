import type { ComponentType } from "react";
import type { Kind } from "../home/kinds";
import { AwgPanel } from "../awg/AwgPanel";
import { PsuPanel } from "../psu/PsuPanel";
import { PsuReadout } from "../psu/PsuReadout";
import { ReadoutStrip } from "../readout/ReadoutStrip";
import { ScopeBody } from "../scope/ScopeBody";

export type KindView = {
  /** What the instrument reports, rendered directly under the header. A kind
   *  may omit it; a readout that has nothing to show returns null itself. */
  readout?: ComponentType;
  /** What you command. Owns its own layout -- the shell imposes no rail and no
   *  canvas, because a power supply wants neither. */
  body: ComponentType;
};

/** The single mapping from an instrument kind to its view. A new kind is an
 *  entry here, not a branch in App.tsx. A kind with no entry falls back to the
 *  shell's "coming soon" box, which is what AWG and DAQ get until they land. */
export const KIND_VIEWS: Partial<Record<Kind, KindView>> = {
  scope: { readout: ReadoutStrip, body: ScopeBody },
  psu: { readout: PsuReadout, body: PsuPanel },
  awg: { body: AwgPanel },
};
