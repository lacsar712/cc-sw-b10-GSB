import os
from datetime import datetime, timedelta, timezone

import psycopg
from jose import JWTError, jwt
from litestar import Litestar, Request, get, post
from litestar.exceptions import HTTPException
from litestar.status_codes import HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN
from passlib.context import CryptContext
from psycopg.rows import dict_row
from psycopg.types.json import Json
from pydantic import BaseModel

from domain import trajectory_diff, trajectory_point

DSN = os.environ.get("DATABASE_URL", "postgresql://app:app@localhost:54395/spectrum")
SECRET = os.environ.get("JWT_SECRET", "spectrum-dev-secret")
pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
USERS = {
    "calibrator": {"role": "writer", "password_hash": pwd.hash("calib123456")},
    "inspector": {"role": "reader", "password_hash": pwd.hash("insp123456")},
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id serial PRIMARY KEY,
    lamp text NOT NULL,
    nominal_nm double precision NOT NULL,
    measured_nm double precision NOT NULL,
    status text NOT NULL,
    verdict text NOT NULL DEFAULT '',
    reason text NOT NULL DEFAULT '',
    created_by text NOT NULL,
    created_at timestamptz NOT NULL
);
"""

SNAPSHOT_SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots (
    id serial PRIMARY KEY,
    title text NOT NULL,
    limit_n int NOT NULL,
    compare_id int,
    points jsonb NOT NULL,
    compare_point jsonb,
    diff jsonb,
    created_by text NOT NULL,
    created_at timestamptz NOT NULL
);
"""

TRAJECTORY_DEFAULT_LIMIT = 10
TRAJECTORY_MAX_LIMIT = 200


def connect():
    return psycopg.connect(DSN, row_factory=dict_row)


class LoginIn(BaseModel):
    username: str
    password: str


class JobIn(BaseModel):
    lamp: str
    nominal_nm: float
    measured_nm: float


class SnapshotIn(BaseModel):
    title: str = ""
    limit: int = TRAJECTORY_DEFAULT_LIMIT
    compare_id: int | None = None


def user_from_request(request: Request) -> dict:
    auth = request.headers.get("Authorization") or ""
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="未登录")
    try:
        payload = jwt.decode(auth[7:], SECRET, algorithms=["HS256"])
    except JWTError as exc:
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="无效令牌") from exc
    if payload.get("sub") not in USERS:
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="无效令牌")
    return {"username": payload["sub"], "role": payload.get("role")}


@get("/api/health")
async def health() -> dict:
    return {"status": "ok", "service": "spectrum-wavelength-desk"}


@post("/api/login")
async def login(data: LoginIn) -> dict:
    u = USERS.get(data.username)
    if not u or not pwd.verify(data.password, u["password_hash"]):
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="账号或密码错误")
    token = jwt.encode(
        {
            "sub": data.username,
            "role": u["role"],
            "exp": datetime.now(timezone.utc) + timedelta(hours=12),
        },
        SECRET,
        algorithm="HS256",
    )
    return {"access_token": token, "role": u["role"], "username": data.username}


@get("/api/jobs")
async def list_jobs(request: Request) -> list:
    user_from_request(request)
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, lamp, nominal_nm, measured_nm, status, verdict, reason, created_by FROM jobs ORDER BY id DESC"
        ).fetchall()
        return list(rows)


@get("/api/jobs/{job_id:int}")
async def get_job(request: Request, job_id: int) -> dict:
    user_from_request(request)
    with connect() as conn:
        row = conn.execute(
            "SELECT id, lamp, nominal_nm, measured_nm, status, verdict, reason, created_by FROM jobs WHERE id = %s",
            (job_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="任务不存在")
        return dict(row)


@post("/api/jobs")
async def create_job(request: Request, data: JobIn) -> dict:
    user = user_from_request(request)
    if user["role"] != "writer":
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="仅校准员可提交")
    with connect() as conn:
        row = conn.execute(
            """
            INSERT INTO jobs(lamp, nominal_nm, measured_nm, status, verdict, reason, created_by, created_at)
            VALUES (%s,%s,%s,'pending','','',%s,%s) RETURNING id
            """,
            (data.lamp.strip(), data.nominal_nm, data.measured_nm, user["username"], datetime.now(timezone.utc)),
        ).fetchone()
        conn.commit()
        return {"id": row["id"], "status": "pending"}


def clamp_limit(limit) -> int:
    try:
        n = int(limit)
    except (TypeError, ValueError):
        n = TRAJECTORY_DEFAULT_LIMIT
    return max(1, min(n, TRAJECTORY_MAX_LIMIT))


def build_trajectory(conn, limit: int, compare_id: int | None) -> dict:
    """近次已结案轨迹 + 可选对照点差额，全部在服务端算好再下发。"""
    rows = conn.execute(
        """
        SELECT id, lamp, nominal_nm, measured_nm, verdict, created_at
        FROM jobs
        WHERE status = 'done'
        ORDER BY created_at DESC, id DESC
        LIMIT %s
        """,
        (limit,),
    ).fetchall()
    points = [trajectory_point(r) for r in rows]
    compare = None
    if compare_id is not None:
        row = conn.execute(
            """
            SELECT id, lamp, nominal_nm, measured_nm, verdict, created_at
            FROM jobs
            WHERE id = %s AND status = 'done'
            """,
            (compare_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="对照点不存在或未结案")
        compare = trajectory_point(row)
    return {
        "limit": limit,
        "points": points,
        "compare": compare,
        "diff": trajectory_diff(points, compare),
    }


@get("/api/trajectory")
async def get_trajectory(
    request: Request, limit: int = TRAJECTORY_DEFAULT_LIMIT, compare_id: int | None = None
) -> dict:
    user_from_request(request)
    with connect() as conn:
        return build_trajectory(conn, clamp_limit(limit), compare_id)


@post("/api/snapshots")
async def create_snapshot(request: Request, data: SnapshotIn) -> dict:
    user = user_from_request(request)
    if user["role"] != "writer":
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="仅校准员可签发")
    limit = clamp_limit(data.limit)
    now = datetime.now(timezone.utc)
    with connect() as conn:
        traj = build_trajectory(conn, limit, data.compare_id)
        title = data.title.strip() or f"轨迹快照 {now.strftime('%Y-%m-%d %H:%M:%S')}"
        row = conn.execute(
            """
            INSERT INTO snapshots(title, limit_n, compare_id, points, compare_point, diff, created_by, created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
            """,
            (
                title,
                limit,
                traj["compare"]["id"] if traj["compare"] else None,
                Json(traj["points"]),
                Json(traj["compare"]) if traj["compare"] else None,
                Json(traj["diff"]) if traj["diff"] else None,
                user["username"],
                now,
            ),
        ).fetchone()
        conn.commit()
    return {
        "id": row["id"],
        "title": title,
        "limit_n": limit,
        "compare_id": traj["compare"]["id"] if traj["compare"] else None,
        "point_count": len(traj["points"]),
        "created_by": user["username"],
        "created_at": now.isoformat(),
    }


@get("/api/snapshots")
async def list_snapshots(request: Request) -> list:
    user_from_request(request)
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, title, limit_n, compare_id, created_by, created_at,
                   jsonb_array_length(points) AS point_count
            FROM snapshots
            ORDER BY id DESC
            """
        ).fetchall()
        return list(rows)


@get("/api/snapshots/{snapshot_id:int}")
async def get_snapshot(request: Request, snapshot_id: int) -> dict:
    user_from_request(request)
    with connect() as conn:
        row = conn.execute(
            """
            SELECT id, title, limit_n, compare_id, points, compare_point, diff, created_by, created_at
            FROM snapshots
            WHERE id = %s
            """,
            (snapshot_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="快照不存在")
        return dict(row)


def on_startup() -> None:
    with connect() as conn:
        conn.execute(SCHEMA)
        conn.execute(SNAPSHOT_SCHEMA)
        n = conn.execute("SELECT COUNT(*) AS n FROM jobs").fetchone()["n"]
        if n == 0:
            now = datetime.now(timezone.utc)
            conn.execute(
                """
                INSERT INTO jobs(lamp, nominal_nm, measured_nm, status, verdict, reason, created_by, created_at)
                VALUES
                ('氦灯-587', 587.56, 587.50, 'done', '合格', '偏差 0.0600 nm 在允差内', 'seed', %s),
                ('汞灯-546', 546.07, 546.30, 'done', '超差', '偏差 0.2300 nm 超过允差 0.08', 'seed', %s)
                """,
                (now, now),
            )
        conn.commit()


app = Litestar(
    route_handlers=[
        health,
        login,
        list_jobs,
        get_job,
        create_job,
        get_trajectory,
        create_snapshot,
        list_snapshots,
        get_snapshot,
    ],
    on_startup=[on_startup],
)
