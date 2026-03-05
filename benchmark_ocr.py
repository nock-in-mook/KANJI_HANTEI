"""
漢字OCRベンチマーク
全教育漢字1026字をフォント画像化し、PaddleOCR + Gemini Flashで判定。
正解率・誤認パターンを記録する。
"""

import os
import sys
import json
import time
import random
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime

# プロジェクトのモジュールを使う
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from education_kanji import KANJI_BY_GRADE, KANJI_TO_GRADE
from kanji_ocr import _run_ocr, is_kanji, gemini_read_kanji, gemini_read_canvas

# --- 設定 ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
IMG_SIZE = 128  # 画像サイズ（正方形）
FONT_SIZE = 96  # フォントサイズ
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "benchmark_results")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# フォント設定（コマンドライン引数で切り替え）
FONT_CONFIGS = {
    "gothic": {
        "name": "ゴシック体",
        "path": "C:/Windows/Fonts/YuGothM.ttc",
        "distort": None,
    },
    "zen_skew": {
        "name": "Zen Kurenaido + 斜め",
        "path": os.path.join(SCRIPT_DIR, "fonts/ZenKurenaido-Regular.ttf"),
        "distort": "skew",
    },
}


def distort_rotate_skew(img: Image.Image) -> Image.Image:
    """回転＋傾き（ノートが斜めだった感じ）"""
    angle = random.uniform(-12, 12)
    rotated = img.rotate(angle, fillcolor="white", expand=False)
    w, h = rotated.size
    skew = random.uniform(-0.15, 0.15)
    coeffs = (1, skew, -skew * h / 2, 0, 1, 0)
    return rotated.transform((w, h), Image.AFFINE, coeffs, fillcolor="white")


def generate_kanji_image(kanji: str, font_path: str, distort: str = None,
                          size: int = IMG_SIZE, font_size: int = FONT_SIZE) -> np.ndarray:
    """漢字1文字をフォント画像として生成する（白背景・黒文字）"""
    img = Image.new("RGB", (size, size), "white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(font_path, font_size)

    # 中央に配置
    bbox = draw.textbbox((0, 0), kanji, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (size - text_w) // 2 - bbox[0]
    y = (size - text_h) // 2 - bbox[1]
    draw.text((x, y), kanji, fill="black", font=font)

    # 崩し適用
    if distort == "skew":
        random.seed(hash(kanji) % 2**32)  # 漢字ごとに異なるが再現可能な崩し
        img = distort_rotate_skew(img)

    return np.array(img)


def test_paddleocr(img_array: np.ndarray) -> list[str]:
    """PaddleOCRで画像を判定し、検出された漢字リストを返す"""
    try:
        results = _run_ocr(img_array)
        kanji_list = []
        for r in results:
            for c in r["text"]:
                if is_kanji(c) and c not in kanji_list:
                    kanji_list.append(c)
        return kanji_list
    except Exception as e:
        return [f"ERROR: {e}"]


def test_gemini(img_array: np.ndarray) -> list[str]:
    """Gemini Flashで画像を判定し、検出された漢字リストを返す"""
    try:
        return gemini_read_canvas(img_array)
    except Exception as e:
        return [f"ERROR: {e}"]


def run_benchmark(config_name: str = "gothic"):
    """全教育漢字のベンチマークを実行"""
    config = FONT_CONFIGS[config_name]
    font_path = config["path"]
    font_name = config["name"]
    distort = config["distort"]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 全漢字リスト
    all_kanji = []
    for grade in sorted(KANJI_BY_GRADE.keys()):
        for k in KANJI_BY_GRADE[grade]:
            all_kanji.append(k)

    total = len(all_kanji)
    print(f"ベンチマーク開始: {total}字")
    print(f"フォント: {font_name} ({font_path})")
    print(f"崩し: {distort or 'なし'}")
    print(f"画像サイズ: {IMG_SIZE}x{IMG_SIZE}, フォントサイズ: {FONT_SIZE}")
    print()

    # 結果格納
    results = []
    ocr_correct = 0
    ocr_errors = []
    gemini_correct = 0
    gemini_errors = []

    # PaddleOCRを先にウォームアップ
    print("PaddleOCR ウォームアップ中...", flush=True)
    warmup_img = generate_kanji_image("山", font_path, distort)
    test_paddleocr(warmup_img)
    print("PaddleOCR 準備完了", flush=True)

    # Geminiウォームアップ
    print("Gemini ウォームアップ中...", flush=True)
    test_gemini(warmup_img)
    print("Gemini 準備完了", flush=True)
    print(flush=True)

    t_start = time.time()

    for i, kanji in enumerate(all_kanji):
        grade = KANJI_TO_GRADE.get(kanji, "?")
        img = generate_kanji_image(kanji, font_path, distort)

        # PaddleOCR
        t0 = time.time()
        ocr_result = test_paddleocr(img)
        t_ocr = time.time() - t0
        ocr_top1 = ocr_result[0] if ocr_result else ""
        ocr_hit = kanji in ocr_result

        if ocr_hit:
            ocr_correct += 1
        else:
            ocr_errors.append({
                "kanji": kanji,
                "grade": grade,
                "top1": ocr_top1,
                "candidates": ocr_result[:5],
            })

        # Gemini（レート制限対策で少し待つ）
        if i > 0 and i % 15 == 0:
            time.sleep(0.5)

        t0 = time.time()
        gemini_result = test_gemini(img)
        t_gem = time.time() - t0
        gemini_top1 = gemini_result[0] if gemini_result else ""
        gemini_hit = kanji in gemini_result

        if gemini_hit:
            gemini_correct += 1
        else:
            gemini_errors.append({
                "kanji": kanji,
                "grade": grade,
                "top1": gemini_top1,
                "candidates": gemini_result[:5],
            })

        # 記録
        results.append({
            "kanji": kanji,
            "grade": grade,
            "ocr_candidates": ocr_result[:5],
            "ocr_top1": ocr_top1,
            "ocr_correct": ocr_hit,
            "gemini_candidates": gemini_result[:5],
            "gemini_top1": gemini_top1,
            "gemini_correct": gemini_hit,
        })

        # 進捗表示（毎回）
        elapsed = time.time() - t_start
        mark = "✓" if ocr_hit else "✗"
        g_mark = "✓" if gemini_hit else "✗"
        err_info = ""
        if not ocr_hit:
            err_info += f" OCR→{ocr_top1 or '空'}"
        if not gemini_hit:
            err_info += f" Gem→{gemini_top1 or '空'}"
        print(f"[{i+1:4d}/{total}] {kanji}({grade}年) OCR:{mark} Gem:{g_mark} ({t_ocr:.1f}s/{t_gem:.1f}s){err_info}", flush=True)

        # 50文字ごとにサマリー
        if (i + 1) % 50 == 0:
            eta = elapsed / (i + 1) * (total - i - 1)
            print(f"  === OCR: {ocr_correct}/{i+1} ({ocr_correct/(i+1)*100:.1f}%) | Gemini: {gemini_correct}/{i+1} ({gemini_correct/(i+1)*100:.1f}%) | 残り約{eta/60:.0f}分 ===", flush=True)

    # --- レポート生成 ---
    report_path = os.path.join(OUTPUT_DIR, f"benchmark_{timestamp}.md")
    json_path = os.path.join(OUTPUT_DIR, f"benchmark_{timestamp}.json")

    # JSON（生データ）
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": timestamp,
            "total": total,
            "config": config_name,
            "font_name": font_name,
            "font_path": font_path,
            "distort": distort,
            "img_size": IMG_SIZE,
            "font_size": FONT_SIZE,
            "ocr_correct": ocr_correct,
            "gemini_correct": gemini_correct,
            "results": results,
        }, f, ensure_ascii=False, indent=2)

    # Markdownレポート
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"# 漢字OCRベンチマーク結果\n\n")
        f.write(f"- 実施日時: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"- 対象: 教育漢字 {total}字\n")
        f.write(f"- フォント: {font_name} ({font_path}, {FONT_SIZE}px)\n")
        f.write(f"- 崩し: {distort or 'なし'}\n")
        f.write(f"- 画像サイズ: {IMG_SIZE}x{IMG_SIZE}px\n\n")

        f.write(f"## 正解率\n\n")
        f.write(f"| エンジン | 正解 | 不正解 | 正解率 |\n")
        f.write(f"|---------|------|--------|--------|\n")
        f.write(f"| PaddleOCR | {ocr_correct} | {total - ocr_correct} | {ocr_correct/total*100:.1f}% |\n")
        f.write(f"| Gemini Flash | {gemini_correct} | {total - gemini_correct} | {gemini_correct/total*100:.1f}% |\n\n")

        f.write(f"## PaddleOCR 誤認リスト ({len(ocr_errors)}字)\n\n")
        if ocr_errors:
            f.write(f"| 正解 | 学年 | 1位候補 | 全候補 |\n")
            f.write(f"|------|------|---------|--------|\n")
            for e in ocr_errors:
                cands = "　".join(e["candidates"][:5]) if e["candidates"] else "（なし）"
                f.write(f"| {e['kanji']} | {e['grade']}年 | {e['top1'] or '（なし）'} | {cands} |\n")
        else:
            f.write("全問正解！\n")

        f.write(f"\n## Gemini Flash 誤認リスト ({len(gemini_errors)}字)\n\n")
        if gemini_errors:
            f.write(f"| 正解 | 学年 | 1位候補 | 全候補 |\n")
            f.write(f"|------|------|---------|--------|\n")
            for e in gemini_errors:
                cands = "　".join(e["candidates"][:5]) if e["candidates"] else "（なし）"
                f.write(f"| {e['kanji']} | {e['grade']}年 | {e['top1'] or '（なし）'} | {cands} |\n")
        else:
            f.write("全問正解！\n")

        f.write(f"\n## 学年別正解率\n\n")
        f.write(f"| 学年 | 字数 | OCR正解 | OCR率 | Gemini正解 | Gemini率 |\n")
        f.write(f"|------|------|---------|-------|-----------|----------|\n")
        for grade in sorted(KANJI_BY_GRADE.keys()):
            grade_results = [r for r in results if r["grade"] == grade]
            g_total = len(grade_results)
            g_ocr = sum(1 for r in grade_results if r["ocr_correct"])
            g_gem = sum(1 for r in grade_results if r["gemini_correct"])
            f.write(f"| {grade}年 | {g_total} | {g_ocr} | {g_ocr/g_total*100:.1f}% | {g_gem} | {g_gem/g_total*100:.1f}% |\n")

    print()
    print(f"=== ベンチマーク完了 ===")
    print(f"PaddleOCR: {ocr_correct}/{total} ({ocr_correct/total*100:.1f}%)")
    print(f"Gemini Flash: {gemini_correct}/{total} ({gemini_correct/total*100:.1f}%)")
    print(f"レポート: {report_path}")
    print(f"生データ: {json_path}")


if __name__ == "__main__":
    config = sys.argv[1] if len(sys.argv) > 1 else "gothic"
    if config not in FONT_CONFIGS:
        print(f"不明な設定: {config}")
        print(f"利用可能: {', '.join(FONT_CONFIGS.keys())}")
        sys.exit(1)
    run_benchmark(config)
