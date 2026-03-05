"""
手書きフォント＋崩しパターンのプレビュー生成
"""

import os
import random
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

IMG_SIZE = 128
FONT_SIZE = 96
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# サンプル漢字
SAMPLES = "花紙緑畳慎歩森鋼穀磁裁縮衆蒸"

# フォント定義
FONTS = {
    "ゴシック(原本)": "C:/Windows/Fonts/YuGothM.ttc",
    "Zen Kurenaido": os.path.join(SCRIPT_DIR, "fonts/ZenKurenaido-Regular.ttf"),
    "Yomogi": os.path.join(SCRIPT_DIR, "fonts/Yomogi-Regular.ttf"),
    "Yusei Magic": os.path.join(SCRIPT_DIR, "fonts/YuseiMagic-Regular.ttf"),
}

def generate_char(kanji: str, font_path: str, size: int = IMG_SIZE, font_size: int = FONT_SIZE) -> Image.Image:
    """漢字1文字を画像化"""
    img = Image.new("RGB", (size, size), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype(font_path, font_size)
    except Exception:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), kanji, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (size - text_w) // 2 - bbox[0]
    y = (size - text_h) // 2 - bbox[1]
    draw.text((x, y), kanji, fill="black", font=font)
    return img


def distort_elastic(img: Image.Image, strength: float = 3.0) -> Image.Image:
    """弾性変形（うねり）"""
    arr = np.array(img).astype(np.float32)
    h, w = arr.shape[:2]
    result = np.full_like(arr, 255)

    # 低周波うねり生成
    dx = np.zeros((h, w), dtype=np.float32)
    dy = np.zeros((h, w), dtype=np.float32)
    for _ in range(4):
        freq_x = random.uniform(0.03, 0.07)
        freq_y = random.uniform(0.03, 0.07)
        amp = random.uniform(strength * 0.5, strength * 1.5)
        phase = random.uniform(0, 6.28)
        ys = np.arange(h).reshape(-1, 1)
        xs = np.arange(w).reshape(1, -1)
        dx += amp * np.sin(freq_y * ys + phase)
        dy += amp * np.cos(freq_x * xs + phase * 0.7)

    # リマッピング
    ys = np.arange(h).reshape(-1, 1)
    xs = np.arange(w).reshape(1, -1)
    src_x = np.clip((xs + dx).astype(int), 0, w - 1)
    src_y = np.clip((ys + dy).astype(int), 0, h - 1)
    result = arr[src_y, src_x]
    return Image.fromarray(result.astype(np.uint8))


def distort_rotate_skew(img: Image.Image) -> Image.Image:
    """回転＋傾き"""
    angle = random.uniform(-12, 12)
    rotated = img.rotate(angle, fillcolor="white", expand=False)
    w, h = rotated.size
    skew = random.uniform(-0.15, 0.15)
    coeffs = (1, skew, -skew * h / 2, 0, 1, 0)
    return rotated.transform((w, h), Image.AFFINE, coeffs, fillcolor="white")


def distort_thick_blur(img: Image.Image) -> Image.Image:
    """太らせ＋ぼかし"""
    big = img.resize((IMG_SIZE * 2, IMG_SIZE * 2), Image.NEAREST)
    result = big.resize((IMG_SIZE, IMG_SIZE), Image.BILINEAR)
    return result.filter(ImageFilter.GaussianBlur(radius=2.0))


def distort_noise(img: Image.Image) -> Image.Image:
    """ノイズ＋薄く"""
    arr = np.array(img).astype(np.float32)
    arr = arr * 0.5 + 255 * 0.5
    noise = np.random.normal(0, 20, arr.shape)
    arr = np.clip(arr + noise, 0, 255)
    return Image.fromarray(arr.astype(np.uint8))


def distort_heavy(img: Image.Image) -> Image.Image:
    """全部盛り（太らせ＋うねり＋回転＋ノイズ）"""
    result = distort_thick_blur(img)
    result = distort_elastic(result, strength=4.0)
    result = distort_rotate_skew(result)
    arr = np.array(result).astype(np.float32)
    noise = np.random.normal(0, 12, arr.shape)
    arr = np.clip(arr + noise, 0, 255)
    return Image.fromarray(arr.astype(np.uint8))


# 崩しパターン
DISTORTIONS = {
    "そのまま": lambda img: img,
    "+うねり": lambda img: distort_elastic(img, 4.0),
    "+太＋ぼかし": distort_thick_blur,
    "+斜め": distort_rotate_skew,
    "+全部盛り": distort_heavy,
}


def create_preview():
    """各フォント × 各崩しパターン × サンプル漢字のプレビュー"""
    n_samples = len(SAMPLES)
    margin = 2
    label_w = 180
    label_h = 24
    section_gap = 10

    # 1フォントあたりの行数 = 崩しパターン数
    rows_per_font = len(DISTORTIONS)

    total_w = label_w + (IMG_SIZE + margin) * n_samples + margin
    total_h = 0
    for _ in FONTS:
        total_h += label_h  # フォント名ヘッダ
        total_h += (IMG_SIZE + margin) * rows_per_font
        total_h += section_gap

    # 上部に漢字ラベル
    total_h += label_h

    canvas = Image.new("RGB", (total_w, total_h), (240, 240, 240))
    draw = ImageDraw.Draw(canvas)

    try:
        label_font = ImageFont.truetype("C:/Windows/Fonts/meiryo.ttc", 13)
        header_font = ImageFont.truetype("C:/Windows/Fonts/meiryob.ttc", 15)
    except Exception:
        label_font = ImageFont.load_default()
        header_font = label_font

    # 上部漢字ラベル
    for j, kanji in enumerate(SAMPLES):
        x = label_w + margin + j * (IMG_SIZE + margin) + IMG_SIZE // 2 - 7
        draw.text((x, 4), kanji, fill="black", font=header_font)

    y_cursor = label_h + 4

    for font_name, font_path in FONTS.items():
        # フォント名ヘッダ（背景色付き）
        draw.rectangle([(0, y_cursor), (total_w, y_cursor + label_h)], fill=(200, 220, 255))
        draw.text((5, y_cursor + 3), f"■ {font_name}", fill="black", font=header_font)
        y_cursor += label_h

        for dist_name, dist_func in DISTORTIONS.items():
            # 崩しパターン名
            draw.text((5, y_cursor + IMG_SIZE // 2 - 7), dist_name, fill="gray", font=label_font)

            random.seed(12345)  # 再現性のためシード固定
            np.random.seed(12345)

            for j, kanji in enumerate(SAMPLES):
                base_img = generate_char(kanji, font_path)
                distorted = dist_func(base_img)

                x = label_w + margin + j * (IMG_SIZE + margin)
                canvas.paste(distorted, (x, y_cursor))

            y_cursor += IMG_SIZE + margin

        y_cursor += section_gap

    output_path = os.path.join(SCRIPT_DIR, "distort_preview.png")
    canvas.save(output_path)
    print(f"プレビュー画像: {output_path}")
    print(f"サイズ: {total_w}x{total_h}px")
    return output_path


if __name__ == "__main__":
    path = create_preview()
    os.startfile(path)
