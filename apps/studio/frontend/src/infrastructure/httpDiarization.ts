import type { DiarizationResult, DiarizationService, SignalPatch } from "../application/ports.ts";
import type { ClusterMapping, Recommendation, Suspicion } from "../domain/types.ts";
import { newId } from "../state/editorStore.ts";

interface RecomputeResponse {
  suspicion: (Suspicion | null)[];
  recommendation: (Recommendation | null)[];
}

interface DiarizeResponse {
  segments: { start: number; end: number; speaker: string }[];
  // segments と同順の怪しさ判定 (混同地図用)。古い backend では欠落しうる。
  suspicion?: Suspicion[];
  // segments と同順の話者候補 (R パネル用)。
  recommendation?: Recommendation[];
  fileId: string;
  clusterMapping?: ClusterMapping[];
  galleryNames?: string[];
}

// backend (/api/diarize) を呼ぶ本番アダプタ。id はここで付与する。
export class HttpDiarization implements DiarizationService {
  constructor(private readonly baseUrl = "/api") {}

  async diarize(
    file: File,
    numSpeakers?: number | null,
    minDurationOn?: number | null,
  ): Promise<DiarizationResult> {
    const form = new FormData();
    form.append("file", file);
    if (numSpeakers != null) form.append("n_speakers", String(numSpeakers));
    if (minDurationOn != null) form.append("min_duration_on", String(minDurationOn));
    const res = await fetch(`${this.baseUrl}/diarize`, { method: "POST", body: form });
    if (!res.ok) {
      throw new Error(`diarize failed: ${res.status} ${res.statusText}`);
    }
    const data = (await res.json()) as DiarizeResponse;
    return {
      segments: data.segments.map((s, i) => {
        const sus = data.suspicion?.[i];
        const rec = data.recommendation?.[i];
        return {
          id: newId(),
          start: s.start,
          end: s.end,
          speaker: s.speaker,
          status: "auto" as const,
          ...(sus ? { suspicion: sus } : {}),
          ...(rec ? { recommendation: rec } : {}),
        };
      }),
      clusterMapping: data.clusterMapping ?? [],
      galleryNames: data.galleryNames ?? [],
    };
  }

  async recompute(
    segments: { id: string; start: number; end: number; speaker: string }[],
  ): Promise<SignalPatch[]> {
    const body = segments.map((s) => ({ start: s.start, end: s.end, speaker: s.speaker }));
    const res = await fetch(`${this.baseUrl}/recompute`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ segments: body }),
    });
    if (res.status === 409) return []; // 分離前 (グリッド無し) → 何もしない
    if (!res.ok) throw new Error(`recompute failed: ${res.status} ${res.statusText}`);
    const data = (await res.json()) as RecomputeResponse;
    // backend は入力順で返す。id を貼り直して patch にする。
    return segments.map((s, i) => ({
      id: s.id,
      suspicion: data.suspicion?.[i] ?? null,
      recommendation: data.recommendation?.[i] ?? null,
    }));
  }
}
