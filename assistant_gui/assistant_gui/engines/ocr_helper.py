from __future__ import annotations

import argparse
import json
import sys

import cv2
import easyocr

try:
    import torch
except Exception:
    torch = None


def should_use_gpu(explicit_value: str) -> bool:
    configured = str(explicit_value or "auto").strip().lower()
    if configured in {"1", "true", "yes", "on"}:
        return True
    if configured in {"0", "false", "no", "off"}:
        return False
    return bool(torch is not None and torch.cuda.is_available())


def run_stdio(gpu_mode: str) -> int:
    reader = easyocr.Reader(["ko", "en"], gpu=should_use_gpu(gpu_mode))
    print("READY", flush=True)
    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
            image_path = str(payload.get("image_path", "")).strip()
            if not image_path:
                raise ValueError("image_path가 비어 있습니다.")
            image = cv2.imread(image_path)
            if image is None:
                raise ValueError("이미지를 읽지 못했습니다.")
            texts = reader.readtext(image, detail=0)
            print(json.dumps({"texts": texts}, ensure_ascii=False), flush=True)
        except Exception as exc:
            print(json.dumps({"texts": [], "error": str(exc)}, ensure_ascii=False), flush=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stdio", action="store_true")
    parser.add_argument("--gpu", default="auto")
    args = parser.parse_args()
    if args.stdio:
        return run_stdio(args.gpu)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())