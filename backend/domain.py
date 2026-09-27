TOLERANCE_NM = 0.08

TRAJECTORY_MAX_LIMIT = 100


def judge(nominal: float, measured: float) -> tuple[str, str]:
    delta = abs(measured - nominal)
    if delta <= TOLERANCE_NM:
        return "合格", f"偏差 {delta:.4f} nm 在允差内"
    return "超差", f"偏差 {delta:.4f} nm 超过允差 {TOLERANCE_NM}"


def clamp_limit(limit: int | None) -> int:
    try:
        n = int(limit)
    except (TypeError, ValueError):
        n = 10
    return max(1, min(n, TRAJECTORY_MAX_LIMIT))


def _iso(value):
    return value.isoformat() if hasattr(value, "isoformat") else value


def shape_point(row: dict, compare: dict | None = None) -> dict:
    """把一条已结案任务整形成轨迹点；给对照点时由服务端算差额。"""
    deviation = row["measured_nm"] - row["nominal_nm"]
    point = {
        "id": row["id"],
        "lamp": row["lamp"],
        "nominal_nm": row["nominal_nm"],
        "measured_nm": row["measured_nm"],
        "deviation_nm": round(deviation, 6),
        "verdict": row["verdict"],
        "created_at": _iso(row["created_at"]),
        "measured_diff_nm": None,
        "deviation_diff_nm": None,
    }
    if compare is not None:
        cmp_deviation = compare["measured_nm"] - compare["nominal_nm"]
        point["measured_diff_nm"] = round(row["measured_nm"] - compare["measured_nm"], 6)
        point["deviation_diff_nm"] = round(deviation - cmp_deviation, 6)
    return point


def build_trajectory(rows: list[dict], compare_row: dict | None, limit: int) -> dict:
    """组装轨迹响应：点集 + 对照点 + 各点差额（全部服务端计算）。"""
    compare = None
    if compare_row is not None:
        compare = shape_point(compare_row)
    return {
        "limit": clamp_limit(limit),
        "compare": compare,
        "points": [shape_point(r, compare_row) for r in rows],
    }
