## 実験: <!-- 実験ID -->

**仮説**: <!-- 1行で -->

## 変更点 (vs ベースライン)

- <!-- config / コードの変更点 -->

## 結果

| Metric | この実験 | ベースライン | Δ |
|---|---|---|---|
| DER (micro) | | | |
| DER (macro) | | | |
| RTF | | | |

実行: `<!-- commit -->` @ <!-- date --> device=<!-- device --> hw=<!-- hw -->

## 結果データ (GCS)

```bash
gcloud storage ls gs://voxmap/experiments/<!-- 実験ID -->/results/
```

<!-- gcloud storage ls の出力をここに貼る -->

## リンク

- ノート: `docs/experiments/<!-- 実験ID -->.md`
- Config: `experiments/<!-- 実験ID -->/config.yaml`

## チェックリスト

- [ ] metrics.json 記録済み
- [ ] docs 考察記入済み
- [ ] GCS アップロード済み
