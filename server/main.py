"""一机一码授权验证服务"""
import secrets
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel

from db import get_conn

app = FastAPI(title="License Verification Service")

ADMIN_PASSWORD = "your_admin_password_here"


class VerifyRequest(BaseModel):
    key: str
    machine_id: str


class GenerateRequest(BaseModel):
    count: int = 1


@app.on_event("startup")
def startup():
    from db import init_db
    init_db()


def _generate_key() -> str:
    """生成 XXXX-XXXX-XXXX-XXXX 格式授权码"""
    parts = [secrets.token_hex(2).upper() for _ in range(4)]
    return "-".join(parts)


@app.post("/api/verify")
def verify(req: VerifyRequest):
    """验证授权码。首次使用绑定机器码。"""
    key = req.key.strip().upper()
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM license_keys WHERE license_key = ?", (key,)
    ).fetchone()

    if not row:
        conn.close()
        return {"ok": False, "msg": "授权码不存在"}

    if row["machine_id"] is None:
        conn.execute(
            "UPDATE license_keys SET machine_id = ?, activated_at = CURRENT_TIMESTAMP WHERE license_key = ?",
            (req.machine_id, key),
        )
        conn.commit()
        conn.close()
        return {"ok": True, "msg": ""}

    if row["machine_id"] != req.machine_id:
        conn.close()
        return {"ok": False, "msg": "授权码与机器不匹配"}

    conn.close()
    return {"ok": True, "msg": ""}


@app.post("/api/generate")
def generate(req: GenerateRequest, authorization: str = Header(None)):
    """批量生成授权码（需要 admin 密码）。"""
    if authorization != f"Bearer {ADMIN_PASSWORD}":
        raise HTTPException(status_code=401, detail="Unauthorized")

    keys = []
    conn = get_conn()
    for _ in range(req.count):
        key = _generate_key()
        conn.execute("INSERT INTO license_keys (license_key) VALUES (?)", (key,))
        keys.append(key)
    conn.commit()
    conn.close()
    return {"ok": True, "keys": keys}


@app.get("/api/keys")
def list_keys(authorization: str = Header(None)):
    """查看所有授权码状态（需要 admin 密码）。"""
    if authorization != f"Bearer {ADMIN_PASSWORD}":
        raise HTTPException(status_code=401, detail="Unauthorized")

    conn = get_conn()
    rows = conn.execute(
        "SELECT license_key, machine_id, created_at, activated_at FROM license_keys ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return {"ok": True, "keys": [dict(r) for r in rows]}
