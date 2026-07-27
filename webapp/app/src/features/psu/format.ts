/** A reading the instrument could not give us is null, and null is NOT zero.
 *  Rendering it as "0.000" is a confident lie about live hardware; "--.--" is
 *  the same "no reading" marker ReadoutStrip uses for a failed measurement. */
export function fmt(value: number | null | undefined): string {
  return typeof value === "number" && !Number.isNaN(value) ? value.toFixed(3) : "--.--";
}
