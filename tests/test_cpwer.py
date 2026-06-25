"""cpWER / WER ラッパ (meeteval) と正規化の検証。"""

from voxmap.eval.cpwer import compute_cpwer, compute_wer, normalize_text


def test_normalize_strips_punctuation_and_case() -> None:
    assert normalize_text("Right. You, Yeah!") == "right you yeah"
    assert normalize_text("it's  fine") == "it's fine"


def test_cpwer_perfect_match_is_zero() -> None:
    ref = {"A": "hello world", "B": "good morning"}
    hyp = {"x": "hello world", "y": "good morning"}
    out = compute_cpwer(ref, hyp)
    assert out["cpwer"] == 0.0


def test_cpwer_finds_speaker_permutation() -> None:
    # hyp の話者ラベルが入れ替わっていても最適置換でマッチ → 誤り 0
    ref = {"A": "alpha beta", "B": "gamma delta"}
    hyp = {"x": "gamma delta", "y": "alpha beta"}
    out = compute_cpwer(ref, hyp)
    assert out["cpwer"] == 0.0
    assert out["scored_speaker"] == 2


def test_cpwer_counts_substitution() -> None:
    ref = {"A": "one two three"}
    hyp = {"x": "one two THREE_WRONG"}
    out = compute_cpwer(ref, hyp)
    assert out["length"] == 3
    assert out["substitutions"] == 1
    assert abs(float(out["cpwer"]) - 1 / 3) < 1e-9


def test_wer_siso_on_text() -> None:
    out = compute_wer("the cat sat on the mat", "the cat sat on the mat")
    assert out["wer"] == 0.0
    out2 = compute_wer("one two three four", "one two three")
    assert out2["length"] == 4
    assert out2["deletions"] == 1
    assert abs(float(out2["wer"]) - 0.25) < 1e-9
