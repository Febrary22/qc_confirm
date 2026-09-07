"""체크 결과들을 종합해 0~100점 품질 점수로 환산한다."""
from __future__ import annotations

from typing import Callable, Dict, Optional


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def _graded_fraction(ratio: Optional[float], fail_threshold: float) -> float:
    """ratio(나쁠수록 큰 값, 0~1)를 '좋음' 비율(0~1)로 변환한다.

    ratio=0 -> 1.0 (만점), ratio>=fail_threshold -> 0.0
    """
    if ratio is None:
        return 1.0
    if fail_threshold <= 0:
        return 1.0 if ratio == 0 else 0.0
    return _clamp(1 - (ratio / fail_threshold))


def _safe_ratio_fraction(check: dict, ratio_getter: Callable[[dict], Optional[float]], fail_threshold: float) -> float:
    """체크 결과에서 안전하게 비율을 추출해 점수 비율로 변환. 실행 오류 등으로 값이 없으면
    상태가 fail이면 0점, 그 외에는 중립값(0.5)으로 처리한다."""
    status = check.get("status", "skipped")
    if status == "skipped":
        return 1.0
    try:
        ratio = ratio_getter(check)
    except Exception:  # noqa: BLE001
        ratio = None
    if ratio is None:
        return 0.0 if status == "fail" else 0.5
    return _graded_fraction(ratio, fail_threshold)


def _metadata_fraction(md: dict) -> float:
    status = md.get("status", "skipped")
    if status == "skipped":
        return 1.0
    ratio = md.get("compliance_ratio")
    if ratio is None:
        return 0.0 if status == "fail" else 0.5
    return _clamp(ratio)


def _avg_ratio(check: dict) -> Optional[float]:
    variables = check.get("variables")
    if not variables:
        return None
    return sum(v["ratio"] for v in variables) / len(variables)


def score_report(checks: Dict[str, dict], cfg: dict) -> dict:
    weights = cfg["weights"]
    thr = cfg["thresholds"]

    fractions = {
        "missing_values": _safe_ratio_fraction(
            checks["missing_values"], lambda c: c.get("summary", {}).get("avg_ratio"), thr["missing"]["fail"]
        ),
        "time_continuity": _safe_ratio_fraction(
            checks["time_continuity"], lambda c: c.get("ratio"), thr["time_gap"]["fail_ratio"]
        ),
        "range_check": _safe_ratio_fraction(checks["range_check"], _avg_ratio, thr["range"]["fail"]),
        "outliers": _safe_ratio_fraction(checks["outliers"], _avg_ratio, thr["outlier"]["fail"]),
        "metadata": _metadata_fraction(checks["metadata"]),
        "duplicates": _safe_ratio_fraction(
            checks["duplicates"], lambda c: c.get("ratio", c.get("row_ratio")), thr["duplicates"]["fail"]
        ),
    }

    weight_sum = sum(weights.values()) or 1
    per_check_scores = {k: round(fractions[k] * weights.get(k, 0), 2) for k in fractions}
    total = round(sum(per_check_scores.values()) / weight_sum * 100, 1)
    total = _clamp(total, 0.0, 100.0)

    if total >= 90:
        grade = "우수 (Excellent)"
    elif total >= 75:
        grade = "양호 (Good)"
    elif total >= 50:
        grade = "보통 (Fair)"
    else:
        grade = "불량 (Poor)"

    return {"total": total, "grade": grade, "per_check": per_check_scores, "weights": weights}
