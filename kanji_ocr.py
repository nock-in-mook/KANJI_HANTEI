"""
kanji_ocr.py - 漢字OCRコアモジュール
画像から漢字を認識する純粋関数。他アプリからimportして使える。
PaddleOCR（メイン）+ Gemini Flash-Lite（フォールバック）の二段構え。
"""

import os
import unicodedata
import cv2
import numpy as np
from PIL import Image, ExifTags
from paddleocr import PaddleOCR
from education_kanji import normalize_kanji

# モジュールレベルでOCRインスタンスを保持（遅延初期化）
_ocr_ja = None
_ocr_ch = None


def _get_ocr_ja():
    """日本語OCRエンジン（日本固有漢字に強い）"""
    global _ocr_ja
    if _ocr_ja is None:
        _ocr_ja = PaddleOCR(
            lang="japan",
            use_angle_cls=True,
            show_log=False,
        )
    return _ocr_ja


def _get_ocr_ch():
    """中国語OCRエンジン（偏の認識に強い）"""
    global _ocr_ch
    if _ocr_ch is None:
        _ocr_ch = PaddleOCR(
            lang="ch",
            use_angle_cls=True,
            show_log=False,
        )
    return _ocr_ch


def fix_exif_rotation(pil_img: Image.Image) -> Image.Image:
    """EXIF Orientation情報に基づいて画像を正しい向きに回転する"""
    try:
        exif = pil_img._getexif()
        if exif is None:
            return pil_img

        # Orientationタグを探す
        orientation_key = None
        for tag, name in ExifTags.TAGS.items():
            if name == "Orientation":
                orientation_key = tag
                break

        if orientation_key is None or orientation_key not in exif:
            return pil_img

        orientation = exif[orientation_key]

        # 回転・反転の適用
        if orientation == 2:
            pil_img = pil_img.transpose(Image.FLIP_LEFT_RIGHT)
        elif orientation == 3:
            pil_img = pil_img.rotate(180, expand=True)
        elif orientation == 4:
            pil_img = pil_img.transpose(Image.FLIP_TOP_BOTTOM)
        elif orientation == 5:
            pil_img = pil_img.rotate(-90, expand=True).transpose(Image.FLIP_LEFT_RIGHT)
        elif orientation == 6:
            pil_img = pil_img.rotate(-90, expand=True)
        elif orientation == 7:
            pil_img = pil_img.rotate(90, expand=True).transpose(Image.FLIP_LEFT_RIGHT)
        elif orientation == 8:
            pil_img = pil_img.rotate(90, expand=True)

    except (AttributeError, KeyError, IndexError):
        pass

    return pil_img


def crop_region(img_array: np.ndarray, bbox, padding_ratio: float = 0.15) -> np.ndarray:
    """
    bboxで指定された領域を余白付きで切り出す。
    padding_ratio: bboxの高さに対する余白の割合。
    """
    h, w = img_array.shape[:2]

    # bboxから矩形の範囲を算出
    xs = [p[0] for p in bbox]
    ys = [p[1] for p in bbox]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)

    # 余白を追加
    box_h = y_max - y_min
    pad = int(box_h * padding_ratio)
    x_min = max(0, int(x_min) - pad)
    y_min = max(0, int(y_min) - pad)
    x_max = min(w, int(x_max) + pad)
    y_max = min(h, int(y_max) + pad)

    return img_array[y_min:y_max, x_min:x_max]


def is_kanji(char: str) -> bool:
    """文字がCJK漢字かどうか判定する"""
    try:
        name = unicodedata.name(char, "")
        return "CJK UNIFIED IDEOGRAPH" in name
    except ValueError:
        return False


def _bbox_height(bbox) -> float:
    """bboxの高さ（文字サイズの指標）を算出する"""
    # bbox: [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
    # 左辺の高さと右辺の高さの平均
    left_h = abs(bbox[3][1] - bbox[0][1])
    right_h = abs(bbox[2][1] - bbox[1][1])
    return (left_h + right_h) / 2


def filter_kanji_regions(
    ocr_results: list[dict],
    min_confidence: float = 0.50,
) -> list[dict]:
    """
    OCR結果から漢字を含むテキスト領域だけを抽出する。
    サイズフィルタで説明文を除外し、各領域に含まれる漢字リストも付与する。

    Returns:
        リスト。各要素は:
        {
            "text": "原テキスト",
            "kanji": ["漢", "字"],  # この領域に含まれる漢字
            "confidence": 0.99,
            "bbox": [[x1,y1], ...],
            "label": "①漢字",  # 表示用ラベル
        }
    """
    if not ocr_results:
        return []

    # サイズフィルタの閾値計算
    heights = [_bbox_height(r["bbox"]) for r in ocr_results]
    max_h = max(heights)
    min_h = min(heights)
    height_threshold = max_h * 0.4 if max_h > min_h * 2 else 0

    regions = []
    idx = 0
    for r in ocr_results:
        h = _bbox_height(r["bbox"])
        if r["confidence"] < min_confidence or h < height_threshold:
            continue

        # この領域に含まれる漢字を抽出（旧字体は自動で新字体に変換）
        kanji_chars = []
        for c in r["text"]:
            if is_kanji(c):
                kanji_chars.append(normalize_kanji(c))
        # 重複除去（変換後に同じ字になった場合）
        kanji_chars = list(dict.fromkeys(kanji_chars))
        if not kanji_chars:
            continue

        idx += 1
        regions.append({
            "text": r["text"],
            "kanji": kanji_chars,
            "confidence": r["confidence"],
            "bbox": r["bbox"],
            "label": f"{idx}",
        })

    return regions


def split_to_single_kanji(
    ocr_results: list[dict],
    min_confidence: float = 0.50,
) -> list[dict]:
    """
    OCR結果を1文字ずつに分解し、漢字のみをフィルタする。

    戦略:
    - bboxの高さ（文字サイズ）で「問題の漢字」と「説明文」を区別する
    - 大きい文字＝ドリルの問題漢字（欲しいもの）
    - 小さい文字＝説明文やルビ（ノイズ）
    - 全テキスト領域の高さの中央値を基準に、その50%未満は説明文として除外
    - 同じ漢字が複数領域で検出された場合は文字サイズが大きい方を優先
    """
    if not ocr_results:
        return []

    # 各テキスト領域の高さを計算
    heights = [_bbox_height(r["bbox"]) for r in ocr_results]
    max_h = max(heights)
    min_h = min(heights)

    # サイズフィルタ: 大きい文字と小さい文字が混在している場合のみ適用
    # 最大と最小の比が2倍以上 → 説明文と問題漢字が混在と判断
    if max_h > min_h * 2:
        height_threshold = max_h * 0.4
    else:
        # 全部同じくらいのサイズ → フィルタなし
        height_threshold = 0

    # 漢字ごとに最も大きい文字サイズの結果を保持
    best: dict[str, dict] = {}

    for r in ocr_results:
        text = r["text"]
        bbox = r["bbox"]
        conf = r["confidence"]
        h = _bbox_height(bbox)

        if conf < min_confidence:
            continue

        if h < height_threshold:
            continue

        for char in text:
            if not is_kanji(char):
                continue

            # 大きい文字を優先（同じ漢字が複数箇所にある場合）
            if char not in best or h > best[char]["_height"]:
                best[char] = {
                    "char": char,
                    "confidence": conf,
                    "bbox": bbox,
                    "source_text": text,
                    "_height": h,
                }

    # _heightは内部用なので削除して返す
    result = []
    for v in best.values():
        del v["_height"]
        result.append(v)

    result.sort(key=lambda x: x["confidence"], reverse=True)
    return result


def draw_bboxes(img_array: np.ndarray, regions: list[dict]) -> np.ndarray:
    """
    画像上に漢字テキスト領域のバウンディングボックスと番号を描画する。
    regionsはfilter_kanji_regionsの戻り値を渡す。
    返り値は描画済み画像（RGB numpy配列）。
    """
    annotated = img_array.copy()
    h, w = annotated.shape[:2]

    font_scale = max(0.8, min(w, h) / 600)
    thickness = max(2, int(font_scale * 2))
    box_thickness = max(2, int(font_scale * 3))

    # 番号ごとに異なる色を使う（視認性向上）
    colors = [
        (255, 80, 80),   # 赤
        (80, 180, 80),   # 緑
        (80, 80, 255),   # 青
        (255, 180, 0),   # オレンジ
        (180, 0, 255),   # 紫
        (0, 200, 200),   # シアン
        (255, 100, 200), # ピンク
        (100, 255, 100), # ライム
    ]

    for i, region in enumerate(regions):
        bbox = region["bbox"]
        pts = np.array(bbox, dtype=np.int32)
        color = colors[i % len(colors)]

        # バウンディングボックス描画
        cv2.polylines(annotated, [pts], True, color, box_thickness)

        # 番号ラベル（左上に大きく）
        label = region["label"]
        label_x = int(pts[0][0])
        label_y = int(pts[0][1]) - 8
        label_y = max(label_y, int(40 * font_scale))

        (tw, th), _ = cv2.getTextSize(
            label, cv2.FONT_HERSHEY_SIMPLEX, font_scale * 1.2, thickness)
        cv2.rectangle(annotated,
                       (label_x - 2, label_y - th - 6),
                       (label_x + tw + 6, label_y + 6),
                       color, -1)
        cv2.putText(annotated, label,
                    (label_x + 2, label_y),
                    cv2.FONT_HERSHEY_SIMPLEX, font_scale * 1.2,
                    (255, 255, 255), thickness)

    return annotated


def preprocess_image(img_array: np.ndarray) -> np.ndarray:
    """
    スマホ撮影画像の前処理（認識精度向上）
    - グレースケール変換
    - コントラスト自動調整（CLAHE）
    - 適応的二値化
    - ノイズ除去（メディアンフィルタ）
    """
    if len(img_array.shape) == 3:
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
    else:
        gray = img_array.copy()

    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)

    denoised = cv2.medianBlur(enhanced, 3)

    binary = cv2.adaptiveThreshold(
        denoised, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        blockSize=11,
        C=2,
    )

    result = cv2.cvtColor(binary, cv2.COLOR_GRAY2RGB)
    return result


def _run_ocr_single(ocr, img_array: np.ndarray) -> list[dict]:
    """単一OCRエンジンで実行して結果リストを返す"""
    result = ocr.ocr(img_array, cls=True)

    candidates = []
    if result and result[0]:
        for item in result[0]:
            bbox, (text, conf) = item
            text = text.strip()
            if text:
                candidates.append({
                    "text": text,
                    "confidence": float(conf),
                    "bbox": bbox,
                })
    return candidates


def _run_ocr(img_array: np.ndarray) -> list[dict]:
    """日本語+中国語モデルの両方でOCR実行し、結果をマージする"""
    ja_results = _run_ocr_single(_get_ocr_ja(), img_array)
    ch_results = _run_ocr_single(_get_ocr_ch(), img_array)

    # 日本語モデルの結果をベースに、中国語モデルの結果を追加
    # 同じ位置のテキストは信頼度が高い方を採用
    merged = list(ja_results)

    for ch_r in ch_results:
        ch_bbox_center = _bbox_center(ch_r["bbox"])

        # 日本語結果に同じ位置のテキストがあるか探す
        found_overlap = False
        for i, ja_r in enumerate(merged):
            ja_bbox_center = _bbox_center(ja_r["bbox"])
            # 中心点が近い（画像幅の10%以内）なら同じ領域とみなす
            dist = ((ch_bbox_center[0] - ja_bbox_center[0]) ** 2 +
                    (ch_bbox_center[1] - ja_bbox_center[1]) ** 2) ** 0.5
            threshold = max(
                _bbox_height(ja_r["bbox"]),
                _bbox_height(ch_r["bbox"]),
            )
            if dist < threshold:
                found_overlap = True
                # 中国語モデルの方が信頼度が高ければ置き換え
                if ch_r["confidence"] > ja_r["confidence"]:
                    merged[i] = ch_r
                break

        if not found_overlap:
            # 日本語モデルにない領域 → 追加
            merged.append(ch_r)

    return merged


def _bbox_center(bbox) -> tuple[float, float]:
    """bboxの中心座標を算出する"""
    xs = [p[0] for p in bbox]
    ys = [p[1] for p in bbox]
    return (sum(xs) / 4, sum(ys) / 4)


def recognize_kanji(
    image,
    use_preprocess: bool = True,
) -> list[dict]:
    """
    画像から漢字を認識する。

    use_preprocess=True の場合、前処理あり/なし両方でOCRを実行し、
    信頼度が高い方の結果を採用する。

    Args:
        image: PIL.Image, numpy配列, またはファイルパス
        use_preprocess: 画像前処理も試すか

    Returns:
        認識結果のリスト。各要素は:
        {
            "text": "漢字テキスト",
            "confidence": 0.99,
            "bbox": [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
        }
        信頼度の高い順にソート済み。
    """
    # 画像をPIL→EXIF補正→numpy配列に変換
    if isinstance(image, str):
        pil_img = Image.open(image)
    elif isinstance(image, Image.Image):
        pil_img = image
    else:
        # numpy配列の場合はEXIF補正不要
        img_array = image
        return _recognize_from_array(img_array, use_preprocess)

    pil_img = fix_exif_rotation(pil_img)
    img_array = np.array(pil_img.convert("RGB"))
    return _recognize_from_array(img_array, use_preprocess)


def _recognize_from_array(img_array: np.ndarray, use_preprocess: bool) -> list[dict]:
    """numpy配列からOCR実行する内部関数"""
    raw_results = _run_ocr(img_array)

    if not use_preprocess:
        raw_results.sort(key=lambda x: x["confidence"], reverse=True)
        return raw_results

    processed = preprocess_image(img_array)
    pre_results = _run_ocr(processed)

    raw_best = max((r["confidence"] for r in raw_results), default=0.0)
    pre_best = max((r["confidence"] for r in pre_results), default=0.0)

    if pre_best > raw_best:
        candidates = pre_results
    else:
        candidates = raw_results

    candidates.sort(key=lambda x: x["confidence"], reverse=True)
    return candidates


def recognize_single_kanji(image, use_preprocess: bool = True) -> tuple[str, float]:
    """
    1文字の漢字を認識する簡易関数。
    Returns: (漢字文字列, 信頼度)。検出できなければ ("", 0.0)。
    """
    results = recognize_kanji(image, use_preprocess)
    if results:
        return results[0]["text"], results[0]["confidence"]
    return "", 0.0


# ==========================================
# Gemini Flash-Lite フォールバック
# ==========================================

def _resize_for_gemini(pil_img: Image.Image, max_size: int = 384) -> Image.Image:
    """
    Geminiのトークンを節約するために画像をリサイズする。
    両辺が384px以下なら258トークン固定（最小コスト）。
    """
    w, h = pil_img.size
    if w <= max_size and h <= max_size:
        return pil_img
    scale = max_size / max(w, h)
    new_w = int(w * scale)
    new_h = int(h * scale)
    return pil_img.resize((new_w, new_h), Image.LANCZOS)


def gemini_read_kanji(img_array: np.ndarray) -> list[str]:
    """
    Gemini 2.5 Flashに短冊画像を送り、漢字を読み取る。
    PaddleOCRで読めなかったときのフォールバック用。
    画像は384px以下にリサイズして送信（トークン節約）。

    Args:
        img_array: 短冊画像のnumpy配列（RGB）

    Returns:
        検出された漢字のリスト。例: ["慎", "浸", "薪"]
        API失敗時は空リスト。
    """
    from google import genai

    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        # shared-envから読み込みを試みる
        env_path = "D:/Dropbox/.claude-sync/shared-env"
        if os.path.exists(env_path):
            with open(env_path, encoding="utf-8") as f:
                for line in f:
                    if line.startswith("GEMINI_API_KEY="):
                        api_key = line.strip().split("=", 1)[1]
                        break
    if not api_key:
        raise ValueError("GEMINI_API_KEY が設定されていません")

    client = genai.Client(api_key=api_key)

    # numpy配列 → PIL Image → リサイズ（384px以下=258トークン固定）
    pil_img = _resize_for_gemini(Image.fromarray(img_array))

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            pil_img,
            "これは小学校の漢字ドリルの一部です。"
            "画像に書かれている漢字を全て読み取ってください。"
            "小学校で習う教育漢字（1〜6年生）を優先してください。"
            "漢字だけをスペース区切りで出力してください。"
            "漢字以外の文字（ひらがな・カタカナ・数字・記号）は含めないでください。"
            "例: 山 川 田",
        ],
        config={"thinking_config": {"thinking_budget": 0}},
    )

    # レスポンスから漢字を抽出（旧字体→新字体に自動変換）
    text = response.text.strip()
    raw = [c for c in text.replace(" ", "").replace("　", "") if is_kanji(c)]
    kanji_list = list(dict.fromkeys(normalize_kanji(c) for c in raw))
    return kanji_list


def gemini_read_handwriting(img_array: np.ndarray) -> list[str]:
    """
    手書き漢字をGemini Flashで読み取る。
    画像全体を768pxにリサイズして直接送信。

    Args:
        img_array: 撮影画像のnumpy配列（RGB）

    Returns:
        検出された漢字のリスト
    """
    from google import genai

    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        env_path = "D:/Dropbox/.claude-sync/shared-env"
        if os.path.exists(env_path):
            with open(env_path, encoding="utf-8") as f:
                for line in f:
                    if line.startswith("GEMINI_API_KEY="):
                        api_key = line.strip().split("=", 1)[1]
                        break
    if not api_key:
        raise ValueError("GEMINI_API_KEY が設定されていません")

    client = genai.Client(api_key=api_key)

    # 768pxにリサイズ（手書きは解像度が必要）
    pil_img = _resize_for_gemini(Image.fromarray(img_array), max_size=768)

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            pil_img,
            "これは小学生が手書きした漢字の練習ノートです。"
            "画像に書かれている漢字を全て読み取ってください。"
            "重要：偏（へん）と旁（つくり）を別々の文字として分解しないでください。"
            "例えば「緑」を「糸」と「録」に分けないでください。1文字の漢字として認識してください。"
            "手書きなので形が崩れている場合がありますが、最も近い漢字を推測してください。"
            "小学校で習う教育漢字（1〜6年生）を優先してください。"
            "漢字だけをスペース区切りで出力してください。"
            "漢字以外の文字（ひらがな・カタカナ・数字・記号）は含めないでください。"
            "例: 山 川 田",
        ],
        config={"thinking_config": {"thinking_budget": 0}},
    )

    text = response.text.strip()
    raw = [c for c in text.replace(" ", "").replace("　", "") if is_kanji(c)]
    kanji_list = list(dict.fromkeys(normalize_kanji(c) for c in raw))
    return kanji_list


def gemini_read_canvas(img_array: np.ndarray) -> list[str]:
    """
    Canvas（指書き）の漢字をGemini Flashで読み取る。
    1枠に1文字が前提。白背景に黒い線。

    Args:
        img_array: Canvas画像のnumpy配列（RGB、300x300）

    Returns:
        候補漢字のリスト（最も近い1文字 + 類似候補）
    """
    from google import genai

    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        env_path = "D:/Dropbox/.claude-sync/shared-env"
        if os.path.exists(env_path):
            with open(env_path, encoding="utf-8") as f:
                for line in f:
                    if line.startswith("GEMINI_API_KEY="):
                        api_key = line.strip().split("=", 1)[1]
                        break
    if not api_key:
        raise ValueError("GEMINI_API_KEY が設定されていません")

    client = genai.Client(api_key=api_key)

    pil_img = Image.fromarray(img_array)

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            pil_img,
            "この画像には手書きの漢字が1文字だけ書かれています。"
            "偏（へん）と旁（つくり）が離れていても、必ず1文字の漢字として読んでください。"
            "最も近いと思う漢字を1つ出力してください。"
            "それに加えて、形が似ている候補があれば最大3つまで追加してください。"
            "小学校で習う教育漢字（1〜6年生）を優先してください。"
            "漢字だけをスペース区切りで出力してください。"
            "例: 紙 氏 低",
        ],
        config={"thinking_config": {"thinking_budget": 0}},
    )

    text = response.text.strip()
    raw = [c for c in text.replace(" ", "").replace("　", "") if is_kanji(c)]
    kanji_list = list(dict.fromkeys(normalize_kanji(c) for c in raw))
    return kanji_list
