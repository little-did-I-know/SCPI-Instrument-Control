import { describe, expect, it } from "vitest";
import { decodeBinaryFrame } from "./binary";

/** Build a frame the way the server does: u32 LE header length, JSON header padded to 4n bytes, float32 LE payload. */
function encode(header: Record<string, unknown>, samples: number[], pad = true): ArrayBuffer {
  let head = new TextEncoder().encode(JSON.stringify({ ...header, n: samples.length, dtype: "f32" }));
  if (pad && head.length % 4 !== 0) head = new Uint8Array([...head, ...new Array(4 - (head.length % 4)).fill(0x20)]);
  const buf = new ArrayBuffer(4 + head.length + samples.length * 4);
  new DataView(buf).setUint32(0, head.length, true);
  new Uint8Array(buf, 4, head.length).set(head);
  const payload = new Float32Array(samples);
  new Uint8Array(buf, 4 + head.length, samples.length * 4).set(new Uint8Array(payload.buffer));
  return buf;
}

describe("decodeBinaryFrame", () => {
  it("decodes header and samples from a padded frame without copying", () => {
    const buf = encode({ type: "waveform", channel: 1, t0: -0.007, dt: 1e-6, seq: 9 }, [0, 0.5, -1.25]);
    const { header, samples } = decodeBinaryFrame(buf);
    expect(header).toMatchObject({ type: "waveform", channel: 1, t0: -0.007, dt: 1e-6, seq: 9, n: 3, dtype: "f32" });
    expect(Array.from(samples)).toEqual([0, 0.5, -1.25]);
    expect(samples.buffer).toBe(buf); // a view, not a copy
  });

  it("copies when the payload offset is not 4-byte aligned", () => {
    const buf = encode({ type: "waveform", channel: "M1", t0: 0, dt: 1 }, [1, 2], false);
    const headerLen = new DataView(buf).getUint32(0, true);
    if ((4 + headerLen) % 4 === 0) return; // this header happened to align; nothing to test
    const { samples } = decodeBinaryFrame(buf);
    expect(Array.from(samples)).toEqual([1, 2]);
    expect(samples.buffer).not.toBe(buf);
  });

  it("decodes an empty clear frame", () => {
    const { header, samples } = decodeBinaryFrame(encode({ type: "waveform", channel: "F1", t0: 0, dt: 1 }, []));
    expect(header.n).toBe(0);
    expect(samples.length).toBe(0);
  });

  it("decodes a reference header", () => {
    const { header } = decodeBinaryFrame(encode({ type: "reference", name: "golden", channel: 2, t0: 0, dt: 1 }, [1]));
    expect(header.type).toBe("reference");
    expect(header.name).toBe("golden");
  });

  it("preserves NaN", () => {
    const { samples } = decodeBinaryFrame(encode({ type: "waveform", channel: 1, t0: 0, dt: 1 }, [NaN, 1]));
    expect(Number.isNaN(samples[0])).toBe(true);
  });

  it("throws on a truncated buffer", () => {
    expect(() => decodeBinaryFrame(new ArrayBuffer(2))).toThrow();
  });

  it("throws when the header length overruns the buffer", () => {
    const buf = new ArrayBuffer(8);
    new DataView(buf).setUint32(0, 100, true);
    expect(() => decodeBinaryFrame(buf)).toThrow();
  });

  it("throws when the payload length disagrees with n", () => {
    const good = encode({ type: "waveform", channel: 1, t0: 0, dt: 1 }, [1, 2, 3]);
    expect(() => decodeBinaryFrame(good.slice(0, good.byteLength - 4))).toThrow();
  });

  it("throws on an unknown dtype", () => {
    const head = new TextEncoder().encode(JSON.stringify({ type: "waveform", channel: 1, t0: 0, dt: 1, n: 0, dtype: "i16" }));
    const buf = new ArrayBuffer(4 + head.length);
    new DataView(buf).setUint32(0, head.length, true);
    new Uint8Array(buf, 4).set(head);
    expect(() => decodeBinaryFrame(buf)).toThrow(/dtype/);
  });
});
