// Decoder for the gateway's dense binary waveform frame (server: scpi_control/server/frames.py):
//   uint32 LE header_len | UTF-8 JSON header (space-padded to 4n bytes) | float32 LE payload
// The server pads the header so the payload starts 4-byte aligned; when it does,
// the samples are a zero-copy view over the socket buffer.

export type BinaryHeader = {
  type: "waveform" | "reference";
  channel: number | string | null;
  t0: number;
  dt: number;
  n: number;
  dtype: "f32";
  seq?: number;
  name?: string | null;
};

export type DecodedFrame = { header: BinaryHeader; samples: Float32Array };

const decoder = new TextDecoder();

export function decodeBinaryFrame(buf: ArrayBuffer): DecodedFrame {
  if (buf.byteLength < 4) throw new Error("binary frame shorter than its length prefix");
  const headerLen = new DataView(buf).getUint32(0, true);
  const offset = 4 + headerLen;
  if (offset > buf.byteLength) throw new Error("binary frame header overruns the buffer");
  const header = JSON.parse(decoder.decode(new Uint8Array(buf, 4, headerLen))) as BinaryHeader;
  if (header.dtype !== "f32") throw new Error(`unsupported sample dtype ${String(header.dtype)}`);
  if (buf.byteLength - offset !== header.n * 4) throw new Error("binary frame payload length does not match header n");
  const samples = offset % 4 === 0 ? new Float32Array(buf, offset, header.n) : new Float32Array(buf.slice(offset, offset + header.n * 4));
  return { header, samples };
}
