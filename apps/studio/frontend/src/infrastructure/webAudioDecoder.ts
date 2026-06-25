import type { AudioDecoder } from "../application/ports.ts";
import { BPS } from "../domain/constants.ts";
import type { DecodedAudio, Peaks } from "../domain/types.ts";

// Web Audio API で decode し、BPS バケット/秒で min/max ピークを事前計算する。
export class WebAudioDecoder implements AudioDecoder {
  async decode(file: File): Promise<DecodedAudio> {
    const arrayBuffer = await file.arrayBuffer();
    const ctx = new AudioContext();
    try {
      const buffer = await ctx.decodeAudioData(arrayBuffer);
      return {
        duration: buffer.duration,
        sampleRate: buffer.sampleRate,
        peaks: computePeaks(buffer, BPS),
      };
    } finally {
      await ctx.close();
    }
  }
}

function computePeaks(buffer: AudioBuffer, bps: number): Peaks {
  const channel = buffer.getChannelData(0);
  const bucketCount = Math.max(1, Math.ceil(buffer.duration * bps));
  const samplesPerBucket = channel.length / bucketCount;
  const min = new Float32Array(bucketCount);
  const max = new Float32Array(bucketCount);

  for (let b = 0; b < bucketCount; b++) {
    const startIdx = Math.floor(b * samplesPerBucket);
    const endIdx = Math.min(channel.length, Math.floor((b + 1) * samplesPerBucket));
    let lo = 0;
    let hi = 0;
    for (let i = startIdx; i < endIdx; i++) {
      const v = channel[i] ?? 0;
      if (v < lo) lo = v;
      if (v > hi) hi = v;
    }
    min[b] = lo;
    max[b] = hi;
  }
  return { min, max, bps };
}
