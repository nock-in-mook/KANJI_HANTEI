# KANJI_HANTEI - 漢字判定

スマホで漢字を写真に撮る → 自動でどの漢字か判別するプログラム。

## 概要

- 入力: 漢字の写真（スマホカメラで撮影）
- 出力: 判別された漢字（文字コード・読みなど）

## 想定する使い方（漢字書き順アプリとの連携）

このプロジェクトは**機能モジュール**として作る。単体アプリではなく、以下の連携を想定：

1. **KANJI_HANTEI**: 写真から正しい漢字を判定
2. **漢字書き順アプリ**: 判定結果を受け取り、その漢字の書き順を表示

```
[漢字の写真] → KANJI_HANTEI（判定） → [漢字] → 漢字書き順アプリ（書き順表示）
```

## 技術スタック

- **OCR**: EasyOCR（日本語対応、永続無料・PDXエラーなし）
- **Webアプリ**: Streamlit

## プロジェクト構成

```
KANJI_HANTEI/
├── README.md
├── requirements.txt
├── app.py              # Streamlit Webアプリ
├── run_with_tunnel.ps1 # スマホ用（Cloudflare Tunnel経由）
├── .streamlit/
│   └── config.toml    # サーバー設定
├── .venv/              # 仮想環境（git管理外）
└── .gitignore
```

## セットアップ・起動

### 1. セットアップ（PDXエラーが出る場合）

```powershell
.\setup_clean.ps1
```

PaddleOCR を完全に削除し、EasyOCR のみをインストールします。

### 1b. 通常のセットアップ

```powershell
cd KANJI_HANTEI
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. 起動（PCのみ）

```powershell
.\.venv\Scripts\Activate.ps1
streamlit run app.py
```

### 3. スマホからアクセスする場合

#### 方法A: 同じWi-Fiの場合

PCとスマホを同じWi-Fiに接続し、以下で起動：

```powershell
.\.venv\Scripts\Activate.ps1
streamlit run app.py
```

- PCのIPアドレスを確認（`ipconfig` で 192.168.x.x）
- スマホで `http://192.168.x.x:8501` にアクセス

#### 方法B: 同じWi-Fiが使えない場合（Cloudflare Tunnel）

インターネット経由で公開。**アカウント登録不要・無料**。

**1. cloudflared をインストール**

```powershell
winget install Cloudflare.cloudflared
```

**2. 1コマンドで起動**

```powershell
.\run.ps1
```

→ ターミナルに **QRコード** が表示される。スマホのカメラでスキャンするだけ（コピペ不要）

### トラブルシューティング

- **同じWi-Fiで接続できない**: ファイアウォールでポート8501を許可するか、方法B（Cloudflare Tunnel）を使う
- **URL**: 同じWi-Fiは `http://`、Cloudflare経由は `https://`

## 開発環境

- Python 3.10
- Windows

## ライセンス

未定
