import { readFile } from 'node:fs/promises';

// Read intrinsic WebP dimensions so HTML reserves the correct space before load.
export async function webpSize(path) {
  const data = await readFile(path);
  if (data.toString('ascii', 0, 4) !== 'RIFF' || data.toString('ascii', 8, 12) !== 'WEBP') throw new Error(`Invalid WebP: ${path}`);
  for (let offset = 12; offset + 8 <= data.length;) {
    const type = data.toString('ascii', offset, offset + 4);
    const size = data.readUInt32LE(offset + 4);
    const start = offset + 8;
    if (type === 'VP8X') return { width: 1 + data.readUIntLE(start + 4, 3), height: 1 + data.readUIntLE(start + 7, 3) };
    if (type === 'VP8 ') return { width: data.readUInt16LE(start + 6) & 0x3fff, height: data.readUInt16LE(start + 8) & 0x3fff };
    if (type === 'VP8L') {
      const bits = data.readUInt32LE(start + 1);
      return { width: 1 + (bits & 0x3fff), height: 1 + ((bits >>> 14) & 0x3fff) };
    }
    offset = start + size + (size % 2);
  }
  throw new Error(`No dimensions found: ${path}`);
}
