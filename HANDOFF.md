# HANDOFF - 漢字判定プロジェクト

## 現在の状況
- Streamlit + PaddleOCR(2.9.1) + Gemini 2.5 Flash-Lite で漢字判定Webアプリが動作中
- PaddleOCR（日本語+中国語デュアルモデル）がメイン、Geminiはフォールバック
- 教育漢字DB 1026字（学年別）+ 類似漢字マッピング 308字を実装済み
- Cloudflare Tunnel経由でスマホアクセス可能

## 技術スタック
- Python 3.10 / Streamlit / PaddleOCR 2.9.1 / PaddlePaddle 2.6.2
- google-genai（Gemini 2.5 Flash-Lite）
- Cloudflare Tunnel（スマホアクセス用）

## 主要ファイル
- `app.py` — Streamlit UI（短冊選択→漢字選択→結果表示の3ステップ）
- `kanji_ocr.py` — OCRコアモジュール（デュアルモデル + Geminiフォールバック）
- `education_kanji.py` — 教育漢字DB + 類似漢字マッピング
- `tunnel_with_qr.py` — Cloudflareトンネル起動

## 次のアクション
- 類似漢字マッピングのブラッシュアップ（バックグラウンドで実行中）
- Geminiモデル比較テスト（Flash-Lite vs Flash）
- 漢字書き順アプリとの連携機能
