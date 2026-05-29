# 授权服务部署指南（腾讯云）

## 第 1 步：登录服务器

1. 打开腾讯云控制台：https://console.cloud.tencent.com/cvm/instance
2. 找到你的服务器实例，点击右侧 **登录** 按钮
3. 选择 **OrcaTerm**（网页终端），会打开一个命令行窗口

## 第 2 步：安装 Docker

复制下面的命令，粘贴到终端里执行：

```bash
curl -fsSL https://get.docker.com | sh
systemctl enable docker
systemctl start docker
```

安装完成后，验证 Docker 是否正常：

```bash
docker --version
```

看到版本号（如 `Docker version 27.x.x`）就说明安装成功。

## 第 3 步：创建项目目录

```bash
mkdir -p /opt/license-server && cd /opt/license-server
```

## 第 4 步：创建文件

逐个复制下面的命令到终端执行，每个命令会创建一个文件。

### 4.1 创建 Dockerfile

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

### 4.2 创建 docker-compose.yml

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

### 4.3 创建 requirements.txt

```bash
cat > requirements.txt << 'EOF'
fastapi>=0.100.0
uvicorn>=0.20.0
EOF
```

### 4.4 创建 db.py

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

### 4.5 创建 main.py

```bash
cat > main.py << 'EOF'
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
    parts = [secrets.token_hex(2).upper() for _ in range(4)]
    return "-".join(parts)


def _check_auth(authorization: str | None):
    if not authorization or not hmac.compare_digest(authorization, f"Bearer {ADMIN_PASSWORD}"):
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.post("/api/verify")
def verify(req: VerifyRequest):
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

## 第 5 步：设置管理密码并启动

把 `你的密码` 换成你想设置的管理密码：

```bash
export ADMIN_PASSWORD="你的密码"
docker compose up -d --build
```

首次启动需要下载依赖和构建镜像，大约 1-2 分钟。

## 第 6 步：放通安全组端口

1. 回到腾讯云控制台 → 云服务器 → 实例
2. 点击实例名称进入详情页
3. 点击上方 **安全组** 标签
4. 点击绑定的安全组名称 → **编辑规则**
5. 添加入站规则：
   - 类型：自定义 TCP
   - 端口：**8080**
   - 来源：**0.0.0.0/0**

## 第 7 步：验证

浏览器打开：

```
http://49.51.75.21:8080/docs
```

看到 FastAPI 自动生成的 API 文档页面，说明部署成功。

## 常用管理命令

```bash
# 查看服务状态
docker compose ps

# 查看日志
docker compose logs -f

# 重启服务
docker compose restart

# 停止服务
docker compose down

# 生成授权码（把密码和数量改成你自己的）
curl -X POST http://localhost:8080/api/generate \
  -H "Authorization: Bearer 你的密码" \
  -H "Content-Type: application/json" \
  -d '{"count": 5}'

# 查看所有授权码
curl http://localhost:8080/api/keys \
  -H "Authorization: Bearer 你的密码"
```
