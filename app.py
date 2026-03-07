"""
KANJI_HANTEI - 漢字判定 Webアプリ
スマホで漢字を撮影 → 短冊で場所を選ぶ → 漢字を選ぶ → 書き順アプリへ
"""

import streamlit as st
from PIL import Image
import numpy as np
from streamlit_drawable_canvas import st_canvas
from kanji_ocr import (
    fix_exif_rotation,
    recognize_kanji,
    filter_kanji_regions,
    crop_region,
    gemini_read_kanji,
    gemini_read_canvas,
)
from education_kanji import get_similar_kanji, get_grade

# ページ設定
st.set_page_config(
    page_title="漢字判定",
    page_icon="\U0001f4dd",
    layout="centered",
)

# スマホ向けCSS + capture="environment"注入
st.markdown("""
<style>
    /* 漢字選択ボタン（大きく・太く・子供が押しやすく） */
    .kanji-grid button {
        font-size: 2.5rem !important;
        padding: 1rem !important;
        min-height: 80px !important;
    }
    /* 短冊の下の選択ボタン */
    .strip-btn button {
        margin-top: -10px !important;
        border-top-left-radius: 0 !important;
        border-top-right-radius: 0 !important;
    }
</style>
<script>
// スマホの背面カメラを優先する
const observer = new MutationObserver(() => {
    document.querySelectorAll(
        'input[type="file"][accept*="image"]'
    ).forEach(el => {
        if (!el.hasAttribute('capture')) {
            el.setAttribute('capture', 'environment');
        }
    });
});
observer.observe(document.body, { childList: true, subtree: true });
</script>
""", unsafe_allow_html=True)

st.title("\U0001f4dd 漢字判定")

# --- モード切り替え ---
mode = st.radio(
    "\u30e2\u30fc\u30c9",
    ["\U0001f4d6 \u5370\u5237", "\U0001f4f7 \u56f2\u3093\u3067\u9078\u3076", "\U0001f58a\ufe0f \u6307\u3067\u66f8\u304f"],
    horizontal=True,
    label_visibility="collapsed",
)
is_canvas = "\u6307\u3067\u66f8\u304f" in mode
is_crop = "\u56f2\u3093\u3067\u9078\u3076" in mode

# ==========================================
# 指で書くモード（Canvas → Gemini）
# ==========================================
if is_canvas:
    selected_kanji = st.session_state.get("selected_kanji", None)
    canvas_candidates = st.session_state.get("canvas_candidates", None)
    has_results = canvas_candidates is not None or selected_kanji is not None

    # Canvas表示（結果がある場合は小さく）
    if has_results:
        st.caption("書き直して再判定できます")
    else:
        st.caption("下の枠に指で漢字を書いてください")

    canvas_size = 150 if has_results else 300
    stroke_w = 4 if has_results else 8

    canvas_result = st_canvas(
        fill_color="rgba(255, 255, 255, 0)",
        stroke_width=stroke_w,
        stroke_color="#000000",
        background_color="#FFFFFF",
        width=canvas_size,
        height=canvas_size,
        drawing_mode="freedraw",
        key="canvas",
    )

    if st.button("\U0001f50d 判定する", use_container_width=True):
        if canvas_result.image_data is not None:
            canvas_img = canvas_result.image_data.astype(np.uint8)
            canvas_rgb = canvas_img[:, :, :3]

            if np.mean(canvas_rgb) > 250:
                st.warning("まだ何も書かれていません")
                st.stop()

            with st.spinner("漢字を判定しています..."):
                try:
                    kanji_list = gemini_read_canvas(canvas_rgb)
                except Exception as e:
                    st.error(f"エラーが発生しました: {e}")
                    st.stop()

            if not kanji_list:
                st.warning("漢字を判定できませんでした")
                st.info("\U0001f4a1 もう少し大きく、はっきり書いてみてください")
            else:
                st.session_state.canvas_candidates = kanji_list
                st.session_state.pop("selected_kanji", None)
                st.rerun()
        else:
            st.warning("まだ何も書かれていません")

    # 漢字選択済み → 結果表示
    if selected_kanji is not None:
        st.success(f"\u2705 選択された漢字: **{selected_kanji}**")
        st.info("\U0001f4dd 書き順アプリに連携する機能は開発中です")

    # 判定結果あり → 候補ボタン表示
    elif canvas_candidates is not None:
        st.subheader("どの漢字？")
        cols_per_row = min(len(canvas_candidates), 4)
        cols = st.columns(cols_per_row)
        for i, kanji in enumerate(canvas_candidates):
            with cols[i % cols_per_row]:
                grade = get_grade(kanji)
                label = f"{kanji}\n({grade}年)" if grade else kanji
                if st.button(label, key=f"cv_kanji_{i}", use_container_width=True):
                    st.session_state.selected_kanji = kanji
                    st.rerun()

    st.stop()

# ==========================================
# 囲んで選ぶモード（写真 → 四角で囲む → Gemini）
# ==========================================
if is_crop:
    selected_kanji = st.session_state.get("selected_kanji", None)
    crop_candidates = st.session_state.get("crop_candidates", None)

    # 漢字選択済み → 結果表示
    if selected_kanji is not None:
        st.success(f"\u2705 \u9078\u629e\u3055\u308c\u305f\u6f22\u5b57: **{selected_kanji}**")
        st.info("\U0001f4dd \u66f8\u304d\u9806\u30a2\u30d7\u30ea\u306b\u9023\u643a\u3059\u308b\u6a5f\u80fd\u306f\u958b\u767a\u4e2d\u3067\u3059")
        if st.button("\U0001f504 \u6700\u521d\u304b\u3089\u3084\u308a\u76f4\u3059", use_container_width=True):
            st.session_state.pop("selected_kanji", None)
            st.session_state.pop("crop_candidates", None)
            st.session_state.pop("crop_img", None)
            st.session_state.upload_gen = st.session_state.get("upload_gen", 0) + 1
            st.rerun()
        st.stop()

    # 候補表示中
    if crop_candidates is not None:
        st.subheader("\u3069\u306e\u6f22\u5b57\uff1f")
        cols_per_row = min(len(crop_candidates), 4)
        cols = st.columns(cols_per_row)
        for i, kanji in enumerate(crop_candidates):
            with cols[i % cols_per_row]:
                grade = get_grade(kanji)
                label = f"{kanji}\n({grade}\u5e74)" if grade else kanji
                if st.button(label, key=f"crop_kanji_{i}", use_container_width=True):
                    st.session_state.selected_kanji = kanji
                    st.rerun()

        if st.button("\U0001f519 \u56f2\u307f\u76f4\u3059", use_container_width=True):
            st.session_state.pop("crop_candidates", None)
            st.rerun()
        st.stop()

    # 画像アップロード
    upload_gen = st.session_state.get("upload_gen", 0)
    crop_img_data = st.file_uploader(
        "\U0001f4f7 \u30bf\u30c3\u30d7\u3057\u3066\u6f22\u5b57\u3092\u64ae\u5f71",
        type=["png", "jpg", "jpeg", "webp"],
        key=f"crop_uploader_{upload_gen}",
    )

    if crop_img_data is None:
        st.info("\U0001f446 \u30bf\u30c3\u30d7\u3057\u3066\u6f22\u5b57\u3092\u64ae\u5f71\u3057\u3066\u304f\u3060\u3055\u3044")
        st.stop()

    # 画像読み込み・EXIF補正
    pil_img = fix_exif_rotation(Image.open(crop_img_data))
    img_rgb = pil_img.convert("RGB")

    # Canvas表示サイズを計算（幅を画面に合わせる）
    canvas_w = 350
    orig_w, orig_h = img_rgb.size
    scale = canvas_w / orig_w
    canvas_h = int(orig_h * scale)
    # 高さが大きすぎたら縮小
    if canvas_h > 600:
        canvas_h = 600
        scale = min(canvas_w / orig_w, canvas_h / orig_h)
        canvas_w = int(orig_w * scale)
        canvas_h = int(orig_h * scale)

    display_img = img_rgb.resize((canvas_w, canvas_h), Image.LANCZOS)

    st.caption("\U0001f447 \u6f22\u5b57\u306e\u3042\u305f\u308a\u3092\u6307\u3067\u56f2\u3093\u3067\u304f\u3060\u3055\u3044")

    canvas_result = st_canvas(
        fill_color="rgba(255, 100, 100, 0.2)",
        stroke_width=3,
        stroke_color="#FF0000",
        background_image=display_img,
        width=canvas_w,
        height=canvas_h,
        drawing_mode="rect",
        key="crop_canvas",
    )

    if st.button("\U0001f50d \u3053\u306e\u6f22\u5b57\u3092\u5224\u5b9a", use_container_width=True):
        # 描画された四角形を取得
        rects = []
        if canvas_result.json_data and canvas_result.json_data.get("objects"):
            for obj in canvas_result.json_data["objects"]:
                if obj.get("type") == "rect":
                    rects.append(obj)

        if not rects:
            st.warning("\u307e\u305a\u6f22\u5b57\u306e\u3042\u305f\u308a\u3092\u56db\u89d2\u3067\u56f2\u3093\u3067\u304f\u3060\u3055\u3044")
            st.stop()

        # 最後に描いた四角形を使用
        rect = rects[-1]
        # Canvas座標 → 元画像座標に変換
        rx = rect["left"] / scale
        ry = rect["top"] / scale
        rw = (rect["width"] * rect.get("scaleX", 1)) / scale
        rh = (rect["height"] * rect.get("scaleY", 1)) / scale

        # 切り出し範囲をクリップ
        x1 = max(0, int(rx))
        y1 = max(0, int(ry))
        x2 = min(orig_w, int(rx + rw))
        y2 = min(orig_h, int(ry + rh))

        if x2 - x1 < 10 or y2 - y1 < 10:
            st.warning("\u56f2\u307f\u304c\u5c0f\u3055\u3059\u304e\u307e\u3059\u3002\u3082\u3046\u5c11\u3057\u5927\u304d\u304f\u56f2\u3093\u3067\u304f\u3060\u3055\u3044")
            st.stop()

        # 元画像から切り出し
        img_array = np.array(img_rgb)
        cropped = img_array[y1:y2, x1:x2]

        st.image(cropped, caption="\u56f2\u3093\u3060\u90e8\u5206", use_container_width=True)

        with st.spinner("\u6f22\u5b57\u3092\u5224\u5b9a\u3057\u3066\u3044\u307e\u3059..."):
            try:
                kanji_list = gemini_read_kanji(cropped)
            except Exception as e:
                st.error(f"\u30a8\u30e9\u30fc\u304c\u767a\u751f\u3057\u307e\u3057\u305f: {e}")
                st.stop()

        if not kanji_list:
            st.warning("\u6f22\u5b57\u3092\u5224\u5b9a\u3067\u304d\u307e\u305b\u3093\u3067\u3057\u305f")
            st.info("\U0001f4a1 \u3082\u3046\u5c11\u3057\u5927\u304d\u304f\u56f2\u3093\u3067\u307f\u3066\u304f\u3060\u3055\u3044")
        else:
            st.session_state.crop_candidates = kanji_list
            st.rerun()

    st.stop()

# --- 画像入力（印刷・手書き撮影共通） ---
# 「やり直す」でアップローダーごとリセットするためキーにカウンタを使う
upload_gen = st.session_state.get("upload_gen", 0)
img_data = st.file_uploader(
    "\U0001f4f7 タップして漢字を撮影 / 画像を選択",
    type=["png", "jpg", "jpeg", "webp"],
    key=f"uploader_{upload_gen}",
)

if img_data is None:
    # ファイルがなくなったら状態もクリア
    st.session_state.pop("selected_region", None)
    st.session_state.pop("selected_kanji", None)
    st.session_state.pop("last_file", None)
    st.info("\U0001f446 タップして漢字を撮影してください")
    st.stop()

# ファイル変更検出 → 選択状態をリセット
file_sig = f"{img_data.name}_{img_data.size}"
if st.session_state.get("last_file") != file_sig:
    st.session_state.last_file = file_sig
    st.session_state.pop("selected_region", None)
    st.session_state.pop("selected_kanji", None)

# EXIF回転補正 → numpy配列に変換
pil_img = fix_exif_rotation(Image.open(img_data))
img_rgb = pil_img.convert("RGB")
img_array = np.array(img_rgb)

# ==========================================
# 印刷モード（PaddleOCR → 短冊選択）
# ==========================================

# 前処理オプション（折りたたみ）
with st.expander("\u2699\ufe0f 設定", expanded=False):
    use_preprocess = st.checkbox("画像前処理（手書き・光ムラ対策）", value=True)

# --- OCR実行 ---
with st.spinner("漢字を探しています..."):
    try:
        results = recognize_kanji(img_array, use_preprocess=use_preprocess)
        regions = filter_kanji_regions(results)
    except Exception as e:
        st.error(f"エラーが発生しました: {e}")
        st.exception(e)
        st.stop()

if not regions:
    st.image(img_rgb, caption="入力画像", use_container_width=True)
    st.warning("漢字を検出できませんでした")

    if st.button("\U0001f916 Gemini に聞いてみる", use_container_width=True):
        with st.spinner("Gemini に聞いています..."):
            try:
                gemini_kanji = gemini_read_kanji(img_array)
            except Exception as e:
                st.error(f"Gemini エラー: {e}")
                gemini_kanji = []

        if gemini_kanji:
            st.subheader("どの漢字？")
            cols_per_row = min(len(gemini_kanji), 4)
            cols = st.columns(cols_per_row)
            for i, kanji in enumerate(gemini_kanji):
                with cols[i % cols_per_row]:
                    grade = get_grade(kanji)
                    label = f"{kanji}\n({grade}年)" if grade else kanji
                    if st.button(label, key=f"fallback_{i}", use_container_width=True):
                        st.session_state.selected_kanji = kanji
                        st.rerun()
        else:
            st.warning("Gemini でも検出できませんでした")
    else:
        st.info("\U0001f4a1 なるべく漢字に近づいて、はっきり写るように撮影してください")
    st.stop()

# 短冊画像を事前に切り出し
strips = [crop_region(img_array, r["bbox"]) for r in regions]

# --- 状態管理 ---
selected_idx = st.session_state.get("selected_region", None)
selected_kanji = st.session_state.get("selected_kanji", None)

# ==========================================
# Step 3: 漢字が選ばれた → 結果表示
# ==========================================
if selected_kanji is not None:
    st.success(f"\u2705 選択された漢字: **{selected_kanji}**")
    st.info("\U0001f4dd 書き順アプリに連携する機能は開発中です")

    if st.button("\U0001f504 最初からやり直す", use_container_width=True):
        st.session_state.pop("selected_region", None)
        st.session_state.pop("selected_kanji", None)
        st.session_state.pop("last_file", None)
        # アップローダーもリセット（新しいキーで再生成される）
        st.session_state.upload_gen = st.session_state.get("upload_gen", 0) + 1
        st.rerun()

# ==========================================
# Step 2: 短冊が選ばれた → 漢字リスト表示
# ==========================================
elif selected_idx is not None:
    # 範囲外チェック（写真を変えた場合など）
    if selected_idx >= len(regions):
        st.session_state.pop("selected_region", None)
        st.rerun()

    region = regions[selected_idx]
    strip = strips[selected_idx]

    # 選択された短冊を表示
    st.image(strip, caption="この中の漢字", use_container_width=True)

    # 漢字ボタンをグリッド表示（大きく・押しやすく）
    st.subheader("どの漢字？")
    kanji_list = region["kanji"]
    cols_per_row = min(len(kanji_list), 4)
    cols = st.columns(cols_per_row)
    for i, kanji in enumerate(kanji_list):
        with cols[i % cols_per_row]:
            grade = get_grade(kanji)
            label = f"{kanji}\n({grade}年)" if grade else kanji
            if st.button(label, key=f"kanji_{i}", use_container_width=True):
                st.session_state.selected_kanji = kanji
                st.rerun()

    st.divider()

    # 操作ボタン
    col1, col2 = st.columns(2)
    with col1:
        if st.button("\U0001f519 選び直す", use_container_width=True):
            st.session_state.pop("selected_region", None)
            st.session_state.pop("selected_kanji", None)
            st.rerun()
    with col2:
        if st.button("\U0001f916 漢字が出てこないよ", use_container_width=True):
            # まずOCR候補の「もしかして」を表示
            all_similar = []
            for kanji in kanji_list:
                for s in get_similar_kanji(kanji):
                    if s not in kanji_list and s not in all_similar:
                        all_similar.append(s)
            if all_similar:
                st.caption("もしかして...")
                s_cols = st.columns(min(len(all_similar), 4))
                for si, sk in enumerate(all_similar):
                    with s_cols[si % len(s_cols)]:
                        if st.button(sk, key=f"similar_{si}", use_container_width=True):
                            st.session_state.selected_kanji = sk
                            st.rerun()

            # Geminiにも聞く
            with st.spinner("Gemini に聞いています..."):
                try:
                    gemini_kanji = gemini_read_kanji(strip)
                except Exception as e:
                    st.error(f"Gemini エラー: {e}")
                    gemini_kanji = []

            if gemini_kanji:
                # 既にOCRで出ている漢字は除外
                new_kanji = [gk for gk in gemini_kanji if gk not in kanji_list]
                if new_kanji:
                    st.success(f"Gemini の追加判定: {'　'.join(new_kanji)}")
                    g_cols = st.columns(min(len(new_kanji), 4))
                    for gi, gk in enumerate(new_kanji):
                        with g_cols[gi % len(g_cols)]:
                            if st.button(gk, key=f"gemini_{gi}", use_container_width=True):
                                st.session_state.selected_kanji = gk
                                st.rerun()
                else:
                    st.info("Gemini も同じ漢字を検出しました")
            elif not all_similar:
                st.warning("候補が見つかりませんでした")

# ==========================================
# Step 1: 短冊一覧（どこに書いてある漢字？）
# ==========================================
else:
    st.subheader("\U0001f4cd どこに書いてある漢字？")
    st.caption("画像の下のボタンで選んでください")

    for idx, (region, strip) in enumerate(zip(regions, strips)):
        # 短冊画像を表示
        st.image(strip, use_container_width=True)
        # その直下に選択ボタン
        if st.button(
            f"\u25b2 ここの漢字（{'　'.join(region['kanji'])}）",
            key=f"strip_{idx}",
            use_container_width=True,
        ):
            st.session_state.selected_region = idx
            st.session_state.pop("selected_kanji", None)
            st.rerun()
