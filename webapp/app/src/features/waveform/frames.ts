export type Frame = { t0: number; dt: number; seq?: number; points: ArrayLike<number> };

const frames = new Map<number | string, Frame>();
const listeners = new Set<() => void>();

export function setFrame(channel: number | string, frame: Frame): void {
  frames.set(channel, frame);
  listeners.forEach((listener) => listener());
}

export function getFrame(channel: number | string): Frame | undefined {
  return frames.get(channel);
}

export function clearFrames(): void {
  frames.clear();
}

export function subscribeFrames(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}
