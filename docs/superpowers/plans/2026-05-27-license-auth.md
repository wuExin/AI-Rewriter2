# 一机一码授权机制 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 AI 文章改写工具中增加一机一码授权机制，启动时校验授权码，未授权弹窗输入，验证通过写入本地文件。

**Architecture:**
- **后端**：新增 `server/` 目录，FastAPI 应用提供授权码生成、查询、验证接口，SQLite 存储。部署到 47.103.28.238:8080。
- **客户端**：新增 `src/license.py` 模块封装全部授权逻辑（机器码生成、在线验证、授权弹窗），在 `src/gui.py` 的 `App.__init__()` 中调用入口方法 `check_license(self)`。

**Tech Stack:**
- 后端：Python 3, FastAPI, uvicorn, SQLite
- 客户端：Python 3, customtkinter, requests, hashlib, uuid, subprocess

---

## Part A: 后端（server/）

### Task 1: 创建 FastAPI 项目结构与数据库

**Files:**
- Create: `server/main.py`
- Create: `server/db.py`

- [ ] **Step 1: 创建 `server/db.py` — SQLite 数据库初始化**

```python
"""授权码数据库"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "license.db")


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
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


init_db()
```

- [ ] **Step 2: 创建 `server/main.py` — FastAPI 应用骨架**

```python
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
```

- [ ] **Step 3: 创建 `server/requirements.txt`**

```
fastapi
uvicorn
```

- [ ] **Step 4: 提交**

```bash
git add server/
git commit -m "feat: add license verification server (FastAPI + SQLite)"
```

---

## Part B: 客户端（src/）

### Task 2: 创建 `src/license.py` — 机器码生成与 License 路径

**Files:**
- Create: `src/license.py`

- [ ] **Step 1: 创建 `src/license.py`，实现 `_get_machine_id()` 和 `_get_license_path()`**

```python
"""一机一码授权模块"""
import hashlib
import os
import subprocess
import sys
import uuid


VERIFY_URL = "http://47.103.28.238:8080/api/verify"


def _get_machine_id() -> str:
    """生成 16 位 hex 机器码。优先用主板序列号，降级用 MAC 地址。"""
    try:
        result = subprocess.run(
            ['wmic', 'baseboard', 'get', 'serialnumber'],
            capture_output=True, text=True, timeout=5,
            creationflags=0x08000000,  # CREATE_NO_WINDOW
        )
        lines = [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
        if len(lines) >= 2:
            sn = lines[1]
            if sn and sn != 'To be filled by O.E.M.' and len(sn) > 3:
                return hashlib.md5(sn.encode()).hexdigest()[:16]
    except Exception:
        pass

    mac = uuid.getnode()
    return hashlib.md5(str(mac).encode()).hexdigest()[:16]


def _get_license_path() -> str:
    """返回 .license 文件路径。"""
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, '.license')
```

- [ ] **Step 2: 提交**

```bash
git add src/license.py
git commit -m "feat: add license module with machine id and license path"
```

---

### Task 3: 实现在线验证 `_verify_license()`

**Files:**
- Modify: `src/license.py`

- [ ] **Step 1: 在 `src/license.py` 末尾追加 `_verify_license` 函数**

```python
import requests


def _verify_license(key: str, machine_id: str) -> tuple[bool, str]:
    """在线验证授权码。返回 (ok, msg)。"""
    payload = {"key": key.strip().upper(), "machine_id": machine_id}
    try:
        r = requests.post(VERIFY_URL, json=payload, timeout=10)
        data = r.json()
        return data.get('ok', False), data.get('msg', '')
    except Exception:
        return False, '网络连接失败，请检查网络后重试'
```

- [ ] **Step 2: 提交**

```bash
git add src/license.py
git commit -m "feat: add online license verification"
```

---

### Task 4: 实现授权弹窗 `_show_license_dialog()`

**Files:**
- Modify: `src/license.py`

- [ ] **Step 1: 在 `src/license.py` 末尾追加 `_show_license_dialog` 函数**

```python
import customtkinter as ctk


def _show_license_dialog(parent, machine_id: str):
    """弹出授权码输入弹窗，最多 3 次机会。成功写入 .license，失败 sys.exit。"""
    dialog = ctk.CTkToplevel(parent)
    dialog.title("授权验证")
    dialog.geometry("450x320")
    dialog.resizable(False, False)
    dialog.transient(parent)
    dialog.grab_set()

    # 居中显示
    dialog.update_idletasks()
    x = parent.winfo_x() + (parent.winfo_width() - 450) // 2
    y = parent.winfo_y() + (parent.winfo_height() - 320) // 2
    dialog.geometry(f"+{x}+{y}")

    ctk.CTkLabel(
        dialog, text="授权验证",
        font=ctk.CTkFont(size=18, weight="bold"),
    ).pack(pady=(20, 10))

    # 机器码显示
    mid_frame = ctk.CTkFrame(dialog)
    mid_frame.pack(fill="x", padx=30, pady=5)
    ctk.CTkLabel(mid_frame, text="机器码：").pack(side="left", padx=(10, 5), pady=8)
    ctk.CTkLabel(
        mid_frame, text=machine_id,
        font=ctk.CTkFont(family="Courier", size=13),
    ).pack(side="left", padx=5, pady=8)

    # 授权码输入
    ctk.CTkLabel(dialog, text="请输入授权码：").pack(pady=(10, 2))
    key_entry = ctk.CTkEntry(dialog, width=300, placeholder_text="XXXX-XXXX-XXXX-XXXX")
    key_entry.pack(pady=5)

    # 状态标签
    status_label = ctk.CTkLabel(dialog, text="", text_color="red")
    status_label.pack(pady=5)

    attempts = {"count": 0}

    def do_verify():
        key = key_entry.get().strip().upper()
        if not key:
            status_label.configure(text="请输入授权码", text_color="red")
            return

        verify_btn.configure(state="disabled", text="验证中...")
        dialog.update()

        ok, msg = _verify_license(key, machine_id)

        if ok:
            license_path = _get_license_path()
            with open(license_path, 'w', encoding='utf-8') as f:
                f.write(key)
            dialog.destroy()
            return

        attempts["count"] += 1
        remaining = 3 - attempts["count"]
        if remaining <= 0:
            dialog.destroy()
            sys.exit(0)

        status_label.configure(
            text=f"{msg}（剩余 {remaining} 次机会）",
            text_color="red",
        )
        verify_btn.configure(state="normal", text="验证")

    verify_btn = ctk.CTkButton(
        dialog, text="验证", fg_color="#2CC985", hover_color="#25A873",
        command=do_verify,
    )
    verify_btn.pack(pady=10)

    key_entry.bind("<Return>", lambda e: do_verify())

    dialog.protocol("WM_DELETE_WINDOW", lambda: sys.exit(0))
    parent.wait_window(dialog)
```

- [ ] **Step 2: 提交**

```bash
git add src/license.py
git commit -m "feat: add license dialog with 3-attempt limit"
```

---

### Task 5: 实现入口方法 `check_license()`

**Files:**
- Modify: `src/license.py`

- [ ] **Step 1: 在 `src/license.py` 末尾追加 `check_license` 函数**

```python
def check_license(parent):
    """入口方法：检查授权，未通过则弹窗。供 App.__init__ 调用。"""
    machine_id = _get_machine_id()
    license_path = _get_license_path()

    if os.path.exists(license_path):
        with open(license_path, 'r', encoding='utf-8') as f:
            saved_key = f.read().strip()

        if saved_key:
            ok, _ = _verify_license(saved_key, machine_id)
            if ok:
                return

    _show_license_dialog(parent, machine_id)
```

- [ ] **Step 2: 提交**

```bash
git add src/license.py
git commit -m "feat: add check_license entry point"
```

---

### Task 6: 集成到 `App.__init__()`

**Files:**
- Modify: `src/gui.py:39-59`

- [ ] **Step 1: 在 `App.__init__()` 中 `super().__init__()` 之后、`ctk.set_appearance_mode` 之前插入授权检查**

在 `src/gui.py` 的 `App.__init__` 方法中，`super().__init__()` 之后加两行：

```python
    def __init__(self):
        super().__init__()

        from .license import check_license
        check_license(self)

        ctk.set_appearance_mode("dark")
```

- [ ] **Step 2: 提交**

```bash
git add src/gui.py
git commit -m "feat: integrate license check into app startup"
```
