# AMI Meeting Corpus

ここの中身は [scripts/download_ami.sh](../../../scripts/download_ami.sh) で取得した AMI コーパスのテスト分割。
git管理外 (data/raw/ は .gitignore)。

## 取得方法

```bash
./scripts/download_ami.sh test     # テスト分割 (16ミーティング, ~3GB)
./scripts/download_ami.sh dev      # 開発分割
./scripts/download_ami.sh train    # 訓練分割 (大きい)
```

## 詳細ドキュメント

[docs/references/datasets/ami.md](../../../docs/references/datasets/ami.md) を参照
(AMIの出典・ライセンス・テスト分割の構成・ハマりポイント・ベンチマーク値の目安など)。

## 構成

```
data/raw/ami/
├── audio/       # *.Mix-Headset.wav
├── rttm/        # 正解RTTM (only_words版)
├── uem/         # 評価対象区間
└── setup/       # pyannote/AMI-diarization-setup の clone
```
