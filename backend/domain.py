TOLERANCE_NM = 0.08


def judge(nominal: float, measured: float) -> tuple[str, str]:
    delta = abs(measured - nominal)
    if delta <= TOLERANCE_NM:
        return "合格", f"偏差 {delta:.4f} nm 在允差内"
    return "超差", f"偏差 {delta:.4f} nm 超过允差 {TOLERANCE_NM}"


def trajectory_point(row: dict) -> dict:
    """已结案任务 -> 轨迹点。偏差由服务端统一计算，前端不得自拼。"""
    created = row.get("created_at")
    if hasattr(created, "isoformat"):
        created = created.isoformat()
    deviation = round(abs(row["measured_nm"] - row["nominal_nm"]), 4)
    return {
        "id": row["id"],
        "lamp": row["lamp"],
        "nominal_nm": row["nominal_nm"],
        "measured_nm": row["measured_nm"],
        "deviation_nm": deviation,
        "verdict": row["verdict"],
        "created_at": created or "",
    }


def trajectory_diff(points: list, compare: dict | None) -> dict | None:
    """对照点差额：最新点及每个轨迹点相对对照点的差额（服务端统一计算）。"""
    if not compare:
        return None

    def vs(p: dict) -> dict:
        return {
            "id": p["id"],
            "nominal_diff_nm": round(p["nominal_nm"] - compare["nominal_nm"], 4),
            "measured_diff_nm": round(p["measured_nm"] - compare["measured_nm"], 4),
            "deviation_diff_nm": round(p["deviation_nm"] - compare["deviation_nm"], 4),
        }

    per_point = [vs(p) for p in points]
    latest = per_point[0] if per_point else None
    return {
        "compare_id": compare["id"],
        "latest_id": latest["id"] if latest else None,
        "nominal_diff_nm": latest["nominal_diff_nm"] if latest else None,
        "measured_diff_nm": latest["measured_diff_nm"] if latest else None,
        "deviation_diff_nm": latest["deviation_diff_nm"] if latest else None,
        "per_point": per_point,
    }
