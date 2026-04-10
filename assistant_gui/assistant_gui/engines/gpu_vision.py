from __future__ import annotations

import os

import cv2


_GPU_STATE: bool | None = None


def _gpu_requested() -> bool:
    configured = os.getenv("ASSISTANT_OPENCV_USE_GPU", "auto").strip().lower()
    if configured in {"1", "true", "yes", "on"}:
        return True
    if configured in {"0", "false", "no", "off"}:
        return False
    return True


def is_gpu_available() -> bool:
    global _GPU_STATE
    if _GPU_STATE is not None:
        return _GPU_STATE
    try:
        _GPU_STATE = bool(
            _gpu_requested()
            and hasattr(cv2, "cuda")
            and cv2.cuda.getCudaEnabledDeviceCount() > 0
        )
    except Exception:
        _GPU_STATE = False
    return _GPU_STATE


def _run_gpu(image, operation):
    if not is_gpu_available():
        return None
    try:
        gpu_mat = cv2.cuda_GpuMat()
        gpu_mat.upload(image)
        result = operation(gpu_mat)
        return result.download()
    except Exception:
        return None


def horizontal_flip(image):
    gpu_result = _run_gpu(image, lambda gpu_mat: cv2.cuda.flip(gpu_mat, 1))
    if gpu_result is not None:
        return gpu_result
    return cv2.flip(image, 1)


def bgr_to_rgb(image):
    gpu_result = _run_gpu(image, lambda gpu_mat: cv2.cuda.cvtColor(gpu_mat, cv2.COLOR_BGR2RGB))
    if gpu_result is not None:
        return gpu_result
    return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)


def bgr_to_gray(image):
    gpu_result = _run_gpu(image, lambda gpu_mat: cv2.cuda.cvtColor(gpu_mat, cv2.COLOR_BGR2GRAY))
    if gpu_result is not None:
        return gpu_result
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)