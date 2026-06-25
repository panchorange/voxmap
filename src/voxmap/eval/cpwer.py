"""cpWER / WER (話者帰属つき ASR の精度) — meeteval をラップする。

der.py が pyannote.metrics をラップするのと同じ方針で、cpWER の計算は自作せず
`meeteval` (CHiME 系の標準実装) に委ねる。

- **cpWER** (concatenated minimum-permutation WER): 話者を最適置換でマッチングしてから
  話者ごとに連結したテキストの WER を取る。ASR 誤り + 話者帰属誤りを合算した統合指標。
- **WER** (speaker-agnostic): 全話者のテキストを時刻順に連結した素の WER。話者帰属を無視
  するので、cpWER との差分が「話者帰属がどれだけ効いたか」を表す (原因分解用)。

入力はどちらも `{speaker: text}` の dict (AttributedTranscript.by_speaker() の形)。
"""

from __future__ import annotations

import re

from voxmap.types import AttributedTranscript

# 英数字とアポストロフィ以外を除去 (句読点・記号)。WER 正規化用。
_NON_WORD = re.compile(r"[^a-z0-9' ]+")
_MULTISPACE = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    """WER スコアリング用の正規化: lowercase + 句読点除去 + 空白圧縮。

    参照 (AMI: mixed case, 句読点別トークンは除外済み) と仮説 (parakeet: "right." の
    ように句読点が語に付着・大文字) を同じ土俵に乗せる。両者に必ず同じ正規化を当てる。
    """
    text = text.lower()
    text = _NON_WORD.sub(" ", text)
    return _MULTISPACE.sub(" ", text).strip()


def compute_cpwer(
    reference: dict[str, str], hypothesis: dict[str, str]
) -> dict[str, float | list[tuple[str, str]]]:
    """cpWER を meeteval で計算し、内訳込みで返す。

    reference / hypothesis は `{speaker: concatenated_text}`。話者ラベルは一致不要
    (meeteval が最適置換 assignment を探す)。
    """
    from meeteval.wer import cp_word_error_rate

    er = cp_word_error_rate(reference, hypothesis)
    return {
        "cpwer": float(er.error_rate) if er.error_rate is not None else 0.0,
        "errors": int(er.errors),
        "length": int(er.length),
        "insertions": int(er.insertions),
        "deletions": int(er.deletions),
        "substitutions": int(er.substitutions),
        "missed_speaker": int(er.missed_speaker),
        "falarm_speaker": int(er.falarm_speaker),
        "scored_speaker": int(er.scored_speaker),
        "assignment": [(str(a), str(b)) for a, b in er.assignment],
    }


def compute_wer(reference: str, hypothesis: str) -> dict[str, float]:
    """speaker-agnostic WER。参照・仮説とも **1 本のテキスト** (siso) を受ける。

    multi-speaker を話者無視で測るなら、呼び出し側で **時刻順に** 全 word を連結して
    渡すこと (話者ブロック順で連結すると並べ替えペナルティで WER が無意味に膨らむ)。
    """
    from meeteval.wer import siso_word_error_rate

    er = siso_word_error_rate(reference, hypothesis)
    return {
        "wer": float(er.error_rate) if er.error_rate is not None else 0.0,
        "errors": int(er.errors),
        "length": int(er.length),
        "insertions": int(er.insertions),
        "deletions": int(er.deletions),
        "substitutions": int(er.substitutions),
    }


def by_speaker_from_attributed(transcript: AttributedTranscript) -> dict[str, str]:
    """AttributedTranscript → {speaker: text} (compute_cpwer の入力形)。薄い helper。"""
    return transcript.by_speaker()
