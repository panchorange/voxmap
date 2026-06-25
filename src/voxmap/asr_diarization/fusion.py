"""word↔speaker の時間結合 (late fusion)。

WhisperX 流の統合では、ASR が出した各 word の時間区間 [start, end] を、diarization が
出した話者区間 (SpeakerTurn) と突き合わせ、**最も時間が重なる話者**をその word に割り当てる。
重なる話者が一人もいない word (無音/未カバー区間に落ちた等) は、最も近い turn の話者に
フォールバックする。話者が一切いない (turns 空) 場合は ``fallback_speaker`` を使う。

純関数なので diarization と ASR の実行順序・並列性に依存しない。直列版でも並列版でも
この関数を共有する。
"""

from __future__ import annotations

from voxmap.types import AttributedTranscript, AttributedWord, Diarization, Transcript


def _overlap(a_start: float, a_end: float, b_start: float, b_end: float) -> float:
    """2 区間の重なり長 (>=0)。"""
    return max(0.0, min(a_end, b_end) - max(a_start, b_start))


def assign_speakers(
    transcript: Transcript,
    diarization: Diarization,
    fallback_speaker: str = "speaker_unknown",
) -> AttributedTranscript:
    """各 word に、時間的に最も重なる話者を割り当てて AttributedTranscript を返す。

    - 重なる turn があればその中で overlap 最大の話者
    - 重なる turn が無ければ word 中心に最も近い turn の話者 (最近傍フォールバック)
    - turns が空なら ``fallback_speaker``
    """
    turns = diarization.turns
    attributed: list[AttributedWord] = []

    for word in transcript.words:
        if not turns:
            speaker = fallback_speaker
        else:
            best_speaker = None
            best_overlap = 0.0
            for turn in turns:
                ov = _overlap(word.start, word.end, turn.segment.start, turn.segment.end)
                if ov > best_overlap:
                    best_overlap = ov
                    best_speaker = turn.speaker

            if best_speaker is None:
                # 重なり無し → word 中心に最も近い turn へ
                center = 0.5 * (word.start + word.end)
                best_speaker = min(
                    turns,
                    key=lambda t: _distance_to_segment(center, t.segment.start, t.segment.end),
                ).speaker

            speaker = best_speaker

        attributed.append(
            AttributedWord(text=word.text, start=word.start, end=word.end, speaker=speaker)
        )

    return AttributedTranscript(words=attributed)


def _distance_to_segment(point: float, seg_start: float, seg_end: float) -> float:
    """点と区間の距離 (区間内なら 0)。"""
    if point < seg_start:
        return seg_start - point
    if point > seg_end:
        return point - seg_end
    return 0.0
