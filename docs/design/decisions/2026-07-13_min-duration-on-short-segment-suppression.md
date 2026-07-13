# 2026-07-13: min_duration_on による短区間抑制をデフォルト採用

ステータス: 採用

## 背景

話者分離の DER 誤りのうち false alarm (fa) は、**区間の短さが最も強い識別信号**である
ことが事前分析で分かっていた (孤立した極短区間ほど誤検出である確率が高い)。pyannote の
`SpeakerDiarizationMixin.to_annotation` は元々 `min_duration_on` (この秒数未満の区間を削除)
を持つが、voxmap の `Diarization31Pipeline` では `0.0` に固定されて未使用だった
([`src/voxmap/pipeline/diarization31.py`](../../../src/voxmap/pipeline/diarization31.py))。

推論エンジン (segmentation / embedding / clustering) を一切変更せず、**後処理のみ**で fa を
削減できるかを、AMI (16) / VoxConverse (230) / MSDWild (145) = 計 391 会議のスイープで検証した。

## 検討した選択肢

1. **現状維持 (0.0 固定)**
   - 利点: 変更なし。
   - 欠点: 既に存在する「無料の改善」を放置する。
2. **pooled DER を最小化する閾値 (0.5秒) を採用**
   - 利点: pooled DER が最も下がる (0.0927 → 0.0903、相対 約 -2.6%)。
   - 欠点: 閾値を上げるほど、削除区間のうち実際に誤りだった割合 (的中率) が下がる。
     AMI では 0.3秒が個別最適で、0.5秒はわずかに悪化方向。
3. **的中率とのバランスを優先する保守的な閾値 (0.3秒) を採用**
   - 利点: 削除区間の的中率が最も高く安全側。区間本数ベースの誤り率では既に大きな改善
     (相対 -23〜-49%)。全データセットで一貫して改善方向 (悪化する組み合わせがない)。
   - 欠点: pooled DER の最小値 (0.5秒時点) と比べると、DER の絶対的な下げ幅はやや小さい。
4. **データセット/ドメインごとに閾値を出し分ける**
   - 利点: 各ドメインの最適値を使い切れる。
   - 欠点: ドメイン判定の仕組みが必要になり、単一 config 値の単純さを失う。pooled 最適
     (0.5秒) との差は各ドメインとも僅少で、複雑さに見合わない。

## 決定

**`min_duration_on` を新規パラメータとして追加し、デフォルト `0.3` 秒・設定可能範囲
`[0.1, 1.0]` (0.0 で無効化) とする。CLI ([`configs/pipeline/baseline.yaml`](../../../configs/pipeline/baseline.yaml))
と studio ([`apps/studio/backend/app/config.yaml`](../../../apps/studio/backend/app/config.yaml))
の両方に明示的に `0.3` を設定する。**

範囲外の値は `Diarization31Pipeline` 構築時 / 呼び出し時に `ValueError` を送出する
(`_validate_min_duration_on`)。studio では呼び出しごとに UI から上書き・無効化できる。

## 理由

- **fine-tune 不要・推論エンジン不変**で得られる改善であり、コストがほぼゼロ。採用しない理由がない。
- **0.3秒 (保守的) を選んだ根拠**:
  - duration (DER) ベースでは 0.3〜0.5秒あたりが最良だが、**AMI だけ 0.3秒が個別最適**で、
    0.5秒からは悪化に転じる (1.0秒では pooled でも悪化)。
  - 区間本数ベースの誤り率では 0.3秒時点で既に**相対 23〜49% の改善** (duration ベースの
    相対改善の 4〜8 倍)。人間が確認・修正すべき項目数の代理指標としては、0.3秒でリターンの
    大半を得ている。
  - 削除区間の的中率は閾値を上げるほど下がる。0.3秒はこのバランスにおいて安全側。
  - **「単一閾値ならどの値が最良か」ではなく「保守的に始めて実害が出ないか」を優先**した。
    pooled DER 最適 (0.5秒) との差は僅少なので、必要になれば後から見直せる。
- **範囲バリデーション [0.1, 1.0]**: 0.1 未満は実質無効化に近く、1.0 超は miss (見逃し) の
  悪化が大きくなる領域。誤操作防止のため境界を明示し、無効化は `0.0` に一本化する。

## 影響・トレードオフ

- **後方互換性**: API は後方互換 (新引数はデフォルト付きオプショナル)。ただしデフォルト config の
  出力区間が変わる (従来は短区間抑制なし)。従来挙動に戻すには config で `min_duration_on: 0.0`。
- **失うもの**: pooled DER を最大化する 0.5秒設定と比べると、DER の絶対的な下げ幅はやや小さい。
- **後から見直すとしたらいつ**: (a) 「隣接マージ」版 (削除でなく話者再割当) で miss 増加を
  抑えられた場合、(b) segmentation の fine-tune が進み短区間抑制の相対価値が下がった場合、
  (c) 実運用フィードバック (studio での取り消し率等) で 0.3秒が保守的すぎる / 攻めすぎと
  分かった場合。

## 関連

- [`src/voxmap/pipeline/diarization31.py`](../../../src/voxmap/pipeline/diarization31.py) — `min_duration_on` の追加とバリデーション
- [`configs/pipeline/baseline.yaml`](../../../configs/pipeline/baseline.yaml) — CLI デフォルト
- [`apps/studio/backend/app/config.yaml`](../../../apps/studio/backend/app/config.yaml) — studio デフォルト
- [`CHANGELOG.md`](../../../CHANGELOG.md) — v0.2.0
