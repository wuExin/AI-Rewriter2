# 授权服务部署指南（腾讯云 Linux）

目标：将授权验证服务部署到腾讯云服务器 `49.51.75.21:8080`

共 5 个文件需要创建：requirements.txt、db.py、Dockerfile、docker-compose.yml、main.py

---

## 第 1 步：登录服务器

腾讯云控制台 → 云服务器 → 实例 → 点击 **登录** → 选择 OrcaTerm 网页终端

---

## 第 2 步：安装 Docker

```bash
curl -fsSL https://get.docker.com | sh
systemctl enable --now docker
```

验证：
```bash
docker --version
```
看到版本号即可。

---

## 第 3 步：创建项目目录

```bash
mkdir -p /opt/license-server && cd /opt/license-server
```

---

## 第 4 步：创建文件（共 6 个文件，逐个粘贴执行）

### 文件 1/6：requirements.txt

```bash
cat > requirements.txt << 'EOF'
fastapi>=0.100.0
uvicorn>=0.20.0
EOF
```

### 文件 2/6：db.py

```bash
cat > db.py << 'EOF'
"""授权码数据库"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "license.db")


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS license_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_key TEXT UNIQUE NOT NULL,
            machine_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            activated_at TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()
EOF
```

### 文件 3/6：Dockerfile

```bash
cat > Dockerfile << 'EOF'
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py db.py ./

RUN mkdir -p /app/data

EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
EOF
```

### 文件 4/6：docker-compose.yml

```bash
cat > docker-compose.yml << 'EOF'
services:
  license:
    build: .
    ports:
      - "8080:8080"
    environment:
      - ADMIN_PASSWORD=${ADMIN_PASSWORD}
    volumes:
      - license-data:/app/data
    restart: unless-stopped

volumes:
  license-data:
EOF
```

### 文件 5/6：admin.html

由于 admin.html 文件较长，建议通过 SCP 从本地上传，或在服务器上用 Python 生成：

```bash
python3 -c "
from pathlib import Path
Path('admin.html').write_text(open('/dev/stdin').read())
" < admin.html
```

或者直接从本地上传：
```bash
# 在本地电脑执行
scp server/admin.html root@49.51.75.21:/opt/license-server/
```

### 文件 6/6：main.py

```bash
cat > main.py << 'EOF'
"""一机一码授权验证服务"""
import hmac
import os
import secrets
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import HTMLResponse
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


class LoginRequest(BaseModel):
    password: str


@asynccontextmanager
async def lifespan(app):
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


@app.get("/admin", response_class=HTMLResponse)
def admin_page():
    html_path = Path(__file__).parent / "admin.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))


@app.post("/api/login")
def login(req: LoginRequest):
    if hmac.compare_digest(req.password, ADMIN_PASSWORD):
        return {"ok": True}
    raise HTTPException(status_code=401, detail="密码错误")


@app.delete("/api/keys/{key}")
def delete_key(key: str, authorization: str = Header(None)):
    _check_auth(authorization)
    conn = get_conn()
    try:
        cursor = conn.execute("DELETE FROM license_keys WHERE license_key = ?", (key.strip().upper(),))
        conn.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="授权码不存在")
    finally:
        conn.close()
    return {"ok": True}


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
EOF
```

---

## 第 5 步：启动服务

把 `你的密码` 改成你想设置的管理密码：

```bash
export ADMIN_PASSWORD="你的密码"
docker compose up -d --build
```

首次启动需要下载依赖和构建镜像，大约 1-2 分钟。

验证服务是否启动成功：
```bash
docker compose ps
```
看到 `license` 状态为 `Up` 即可。

---

## 第 6 步：腾讯云安全组放通 8080 端口

在腾讯云控制台（网页）操作：

1. 云服务器 → 实例 → 点击实例名称
2. 上方点击 **安全组** 标签
3. 点击绑定的安全组名称 → **编辑规则**
4. 添加入站规则：
   - 类型：**自定义 TCP**
   - 端口：**8080**
   - 来源：**0.0.0.0/0**

---

## 第 7 步：验证部署

服务器内验证：
```bash
curl http://localhost:8080/docs
```

本地浏览器验证，打开以下地址：
```
http://49.51.75.21:8080/docs
```

看到 FastAPI 自动生成的 API 文档页面，说明部署成功。

---

## 生成授权码

部署成功后，生成授权码分发给用户：

```bash
# 生成 5 个授权码（把密码改成你自己的）
curl -X POST http://localhost:8080/api/generate \
  -H "Authorization: Bearer 你的密码" \
  -H "Content-Type: application/json" \
  -d '{"count": 5}'
```

查看所有授权码状态：
```bash
curl http://localhost:8080/api/keys \
  -H "Authorization: Bearer 你的密码"
```

---

## 常用管理命令

```bash
cd /opt/license-server

# 查看服务状态
docker compose ps

# 查看日志
docker compose logs -f

# 重启服务
docker compose restart

# 停止服务
docker compose down

# 重新构建并启动（代码更新后）
docker compose up -d --build
```
