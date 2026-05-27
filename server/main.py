"""一机一码授权验证服务"""
import hmac
import os
import secrets
import sqlite3
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel, Field

from db import get_conn, init_db

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
if not ADMIN_PASSWORD:
    raise RuntimeError("ADMIN_PASSWORD environment variable is required")


class VerifyRequest(BaseModel):
    key: str
    machine_id: str = Field(..., pattern=r"^[0-9a-fA-F]{16}$")


class GenerateRequest(BaseModel):
    count: int = Field(default=1, ge=1, le=100)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(title="License Verification Service", lifespan=lifespan)


def _generate_key() -> str:
    """生成 XXXX-XXXX-XXXX-XXXX 格式授权码"""
    parts = [secrets.token_hex(2).upper() for _ in range(4)]
    return "-".join(parts)


def _check_auth(authorization: str | None):
    if not authorization or not hmac.compare_digest(authorization, f"Bearer {ADMIN_PASSWORD}"):
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.post("/api/verify")
def verify(req: VerifyRequest):
    """验证授权码。首次使用绑定机器码。"""
    key = req.key.strip().upper()
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM license_keys WHERE license_key = ?", (key,)
        ).fetchone()

        if not row:
            return {"ok": False, "msg": "授权码不存在"}

        if row["machine_id"] is None:
            conn.execute(
                "UPDATE license_keys SET machine_id = ?, activated_at = CURRENT_TIMESTAMP WHERE license_key = ?",
                (req.machine_id, key),
            )
            conn.commit()
            return {"ok": True, "msg": ""}

        if row["machine_id"] != req.machine_id:
            return {"ok": False, "msg": "授权码与机器不匹配"}

        return {"ok": True, "msg": ""}
    finally:
        conn.close()


@app.post("/api/generate")
def generate(req: GenerateRequest, authorization: str = Header(None)):
    """批量生成授权码（需要 admin 密码）。"""
    _check_auth(authorization)

    keys = []
    conn = get_conn()
    try:
        for _ in range(req.count):
            for _attempt in range(3):
                key = _generate_key()
                try:
                    conn.execute("INSERT INTO license_keys (license_key) VALUES (?)", (key,))
                    keys.append(key)
                    break
                except sqlite3.IntegrityError:
                    continue
        conn.commit()
    finally:
        conn.close()
    return {"ok": True, "keys": keys}


@app.get("/api/keys")
def list_keys(authorization: str = Header(None)):
    """查看所有授权码状态（需要 admin 密码）。"""
    _check_auth(authorization)

    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT license_key, machine_id, created_at, activated_at FROM license_keys ORDER BY id DESC"
        ).fetchall()
    finally:
        conn.close()
    return {"ok": True, "keys": [dict(r) for r in rows]}
