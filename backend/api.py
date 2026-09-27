import os
from datetime import datetime, timedelta, timezone

import psycopg
from jose import JWTError, jwt
from litestar import Litestar, Request, get, post
from litestar.exceptions import HTTPException
from litestar.status_codes import HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN
from passlib.context import CryptContext
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from pydantic import BaseModel

from domain import build_trajectory, clamp_limit

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
CREATE TABLE IF NOT EXISTS trajectory_snapshots (
    id serial PRIMARY KEY,
    compare_id integer,
    payload jsonb NOT NULL,
    created_by text NOT NULL,
    created_at timestamptz NOT NULL
);
"""


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
    limit: int = 10
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


def fetch_trajectory(conn, limit: int, compare_id: int | None) -> dict:
    """近次已结案轨迹：按时间倒序取条数，对照点差额全在服务端算。"""
    limit = clamp_limit(limit)
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
    compare_row = None
    if compare_id is not None:
        compare_row = conn.execute(
            """
            SELECT id, lamp, nominal_nm, measured_nm, verdict, created_at
            FROM jobs
            WHERE id = %s AND status = 'done'
            """,
            (compare_id,),
        ).fetchone()
        if not compare_row:
            raise HTTPException(status_code=404, detail="对照点不存在或尚未结案")
    return build_trajectory(rows, compare_row, limit)


@get("/api/trajectory")
async def get_trajectory(request: Request, limit: int = 10, compare_id: int | None = None) -> dict:
    user_from_request(request)
    with connect() as conn:
        return fetch_trajectory(conn, limit, compare_id)


@post("/api/trajectory/snapshots")
async def create_snapshot(request: Request, data: SnapshotIn) -> dict:
    user = user_from_request(request)
    if user["role"] != "writer":
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="仅校准员可签发")
    with connect() as conn:
        payload = fetch_trajectory(conn, data.limit, data.compare_id)
        row = conn.execute(
            """
            INSERT INTO trajectory_snapshots(compare_id, payload, created_by, created_at)
            VALUES (%s, %s, %s, %s) RETURNING id, created_at
            """,
            (
                data.compare_id,
                Jsonb(payload),
                user["username"],
                datetime.now(timezone.utc),
            ),
        ).fetchone()
        conn.commit()
        return {"id": row["id"], "created_at": row["created_at"]}


@get("/api/trajectory/snapshots")
async def list_snapshots(request: Request) -> list:
    user_from_request(request)
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, compare_id, created_by, created_at,
                   jsonb_array_length(payload->'points') AS point_count
            FROM trajectory_snapshots
            ORDER BY id DESC
            """
        ).fetchall()
        return list(rows)


@get("/api/trajectory/snapshots/{snap_id:int}")
async def get_snapshot(request: Request, snap_id: int) -> dict:
    user_from_request(request)
    with connect() as conn:
        row = conn.execute(
            "SELECT id, payload, created_by, created_at FROM trajectory_snapshots WHERE id = %s",
            (snap_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="快照不存在")
        return {
            "id": row["id"],
            "created_by": row["created_by"],
            "created_at": row["created_at"],
            **row["payload"],
        }


def on_startup() -> None:
    with connect() as conn:
        conn.execute(SCHEMA)
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
