import type { SpectrumFrame } from "../../api/types";

let current: SpectrumFrame | null = null;
const listeners = new Set<() => void>();

export function setSpectrum(frame: SpectrumFrame | null): void {
  current = frame;
  listeners.forEach((listener) => listener());
}

export function getSpectrum(): SpectrumFrame | null {
  return current;
}

export function clearSpectrum(): void {
  current = null;
}

export function subscribeSpectrum(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}
