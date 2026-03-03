"""
KANJI_HANTEI - 漢字判定 Webアプリ
スマホで漢字を撮影 → 判定 → 漢字書き順アプリに渡す想定
"""

import streamlit as st
import easyocr
from PIL import Image
import numpy as np

# ページ設定
st.set_page_config(
    page_title="漢字判定",
    page_icon="📝",
    layout="centered",
)

st.title("📝 漢字判定")
st.caption("漢字の写真を撮るか、画像をアップロードしてください。判定された漢字を漢字書き順アプリに渡せます。")

# OCRエンジン（初回のみ読み込み、キャッシュ）- EasyOCR（PDXエラー回避）
@st.cache_resource
def load_ocr():
    return easyocr.Reader(["ja"], gpu=False)

# 入力方法選択
input_method = st.radio(
    "入力方法",
    ["📷 カメラで撮影", "📁 画像をアップロード"],
    horizontal=True,
)

img_data = None

if input_method == "📷 カメラで撮影":
    img_data = st.camera_input("漢字を撮影")
else:
    img_data = st.file_uploader(
        "漢字の画像を選択",
        type=["png", "jpg", "jpeg", "webp"],
    )

if img_data is not None:
    # 画像を表示
    img = Image.open(img_data).convert("RGB")
    img_array = np.array(img)

    col1, col2 = st.columns(2)
    with col1:
        st.image(img, caption="入力画像", use_container_width=True)

    with col2:
        if st.button("🔍 判定する", type="primary"):
            with st.spinner("判定中..."):
                try:
                    reader = load_ocr()
                    result = reader.readtext(img_array)

                    texts = []
                    for (bbox, text, conf) in result:
                        if text.strip():
                            texts.append((text.strip(), conf))

                    if texts:
                        # 1文字の漢字を想定：最初の結果をメインに
                        main_kanji = texts[0][0] if texts else ""
                        confidence = texts[0][1] if texts else 0

                        st.success(f"**判定結果: {main_kanji}**")
                        st.metric("信頼度", f"{confidence:.1%}")

                        if len(texts) > 1:
                            st.write("その他の候補:")
                            for t, c in texts[1:]:
                                st.write(f"- {t} ({c:.1%})")

                        # 漢字書き順アプリに渡す用の出力
                        st.divider()
                        st.subheader("漢字書き順アプリ用")
                        st.code(main_kanji, language=None)
                        st.caption("この文字を漢字書き順アプリに渡してください")

                    else:
                        st.warning("漢字を検出できませんでした。もう一度撮影してみてください。")

                except Exception as e:
                    st.error(f"エラーが発生しました: {e}")
                    st.exception(e)

else:
    st.info("👆 カメラで撮影するか、画像をアップロードしてください")
