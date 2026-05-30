# 管理后台更新部署指南

在已部署授权服务的基础上，更新代码以支持管理网页。

HTML 已嵌入 main.py，需要更新 2 个文件：main.py 和 Dockerfile。

## 操作步骤

### 第 1 步：登录服务器

腾讯云控制台 → 云服务器 → 实例 → 登录 → OrcaTerm

### 第 2 步：更新 Dockerfile

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

### 第 3 步：更新 main.py

```bash
cd /opt/license-server
```

先清空文件：
```bash
> main.py
```

然后分 3 段粘贴（每段单独复制执行）：

**第 1 段：**
```bash
cat >> main.py << 'PYEOF'
"""一机一码授权验证服务"""
import hmac
import os
import secrets
import sqlite3
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from db import get_conn, init_db

ADMIN_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>授权码管理</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, "Microsoft YaHei", sans-serif; background: #f5f5f5; color: #333; }
.login-wrap { display: flex; justify-content: center; align-items: center; height: 100vh; }
.login-box { background: #fff; padding: 40px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,.1); width: 360px; }
.login-box h2 { text-align: center; margin-bottom: 24px; font-size: 20px; }
.login-box input { width: 100%; padding: 10px 12px; border: 1px solid #ddd; border-radius: 4px; font-size: 14px; margin-bottom: 16px; }
.login-box button { width: 100%; padding: 10px; background: #4a90d9; color: #fff; border: none; border-radius: 4px; font-size: 15px; cursor: pointer; }
.login-box button:hover { background: #357abd; }
.login-error { color: #e74c3c; font-size: 13px; margin-bottom: 12px; display: none; }
.admin-wrap { max-width: 900px; margin: 0 auto; padding: 20px; }
.admin-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.admin-header h1 { font-size: 22px; }
.admin-header button { padding: 6px 16px; background: #aaa; color: #fff; border: none; border-radius: 4px; cursor: pointer; font-size: 13px; }
.admin-header button:hover { background: #888; }
.toolbar { display: flex; gap: 10px; align-items: center; margin-bottom: 16px; flex-wrap: wrap; }
.toolbar input { width: 70px; padding: 8px; border: 1px solid #ddd; border-radius: 4px; font-size: 14px; }
.toolbar button { padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer; font-size: 14px; }
.btn-generate { background: #27ae60; color: #fff; }
.btn-generate:hover { background: #219a52; }
.btn-refresh { background: #4a90d9; color: #fff; }
.btn-refresh:hover { background: #357abd; }
.btn-export { background: #8e44ad; color: #fff; }
.btn-export:hover { background: #7d3c98; }
table { width: 100%; border-collapse: collapse; background: #fff; border-radius: 6px; overflow: hidden; box-shadow: 0 1px 4px rgba(0,0,0,.08); }
th, td { padding: 10px 12px; text-align: left; font-size: 13px; border-bottom: 1px solid #eee; }
th { background: #fafafa; font-weight: 600; color: #666; }
tr:last-child td { border-bottom: none; }
tr:hover { background: #f8f9fa; }
.status-active { color: #27ae60; font-weight: 600; }
.status-unused { color: #999; }
.btn-copy, .btn-delete { padding: 3px 10px; border: none; border-radius: 3px; cursor: pointer; font-size: 12px; }
.btn-copy { background: #ecf0f1; color: #333; }
.btn-copy:hover { background: #dfe6e9; }
.btn-delete { background: #fff0f0; color: #e74c3c; }
.btn-delete:hover { background: #fde2e2; }
.empty-row td { text-align: center; color: #999; padding: 40px; }
.toast { position: fixed; top: 20px; left: 50%; transform: translateX(-50%); background: #333; color: #fff; padding: 10px 24px; border-radius: 4px; font-size: 14px; z-index: 999; display: none; }
.hidden { display: none !important; }
</style>
PYEOF
```

**第 2 段：**
```bash
cat >> main.py << 'PYEOF'
</head>
<body>
<div id="toast" class="toast"></div>
<div id="loginPage" class="login-wrap">
  <div class="login-box">
    <h2>授权码管理</h2>
    <div id="loginError" class="login-error">密码错误</div>
    <input type="password" id="passwordInput" placeholder="请输入管理密码" autofocus>
    <button onclick="doLogin()">登 录</button>
  </div>
</div>
<div id="adminPage" class="admin-wrap hidden">
  <div class="admin-header">
    <h1>授权码管理</h1>
    <button onclick="doLogout()">退出登录</button>
  </div>
  <div class="toolbar">
    <span>生成</span>
    <input type="number" id="genCount" value="1" min="1" max="100">
    <span>个</span>
    <button class="btn-generate" onclick="doGenerate()">生成授权码</button>
    <button class="btn-refresh" onclick="loadKeys()">刷新</button>
    <button class="btn-export" onclick="doExport()">导出全部</button>
  </div>
  <table>
    <thead><tr><th>授权码</th><th>状态</th><th>机器码</th><th>创建时间</th><th>激活时间</th><th>操作</th></tr></thead>
    <tbody id="keyTable"><tr class="empty-row"><td colspan="6">加载中...</td></tr></tbody>
  </table>
</div>
<script>
function getToken(){return sessionStorage.getItem('admin_token')}
function authHeaders(){return{'Authorization':'Bearer '+getToken(),'Content-Type':'application/json'}}
function showToast(m,d){var t=document.getElementById('toast');t.textContent=m;t.style.display='block';setTimeout(function(){t.style.display='none'},d||2000)}
function doLogin(){var p=document.getElementById('passwordInput').value.trim();if(!p)return;fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:p})}).then(function(r){return r.json()}).then(function(d){if(d.ok){sessionStorage.setItem('admin_token',p);document.getElementById('loginPage').classList.add('hidden');document.getElementById('adminPage').classList.remove('hidden');document.getElementById('loginError').style.display='none';loadKeys()}else{document.getElementById('loginError').style.display='block'}})}
document.getElementById('passwordInput').addEventListener('keydown',function(e){if(e.key==='Enter')doLogin()});
function doLogout(){sessionStorage.removeItem('admin_token');document.getElementById('adminPage').classList.add('hidden');document.getElementById('loginPage').classList.remove('hidden');document.getElementById('passwordInput').value=''}
if(getToken()){fetch('/api/keys',{headers:authHeaders()}).then(function(r){if(r.ok){document.getElementById('loginPage').classList.add('hidden');document.getElementById('adminPage').classList.remove('hidden');loadKeys()}})}
function loadKeys(){fetch('/api/keys',{headers:authHeaders()}).then(function(r){if(r.status===401){doLogout();return}return r.json()}).then(function(d){if(!d||!d.ok)return;var tb=document.getElementById('keyTable');if(d.keys.length===0){tb.innerHTML='<tr class="empty-row"><td colspan="6">暂无授权码</td></tr>';return}var h='';d.keys.forEach(function(k){var a=!!k.machine_id;var sc=a?'status-active':'status-unused';var st=a?'已激活':'未使用';var cb=a?'':'<button class="btn-copy" onclick="copyKey(\''+k.license_key+'\')">复制</button>';h+='<tr><td><code>'+k.license_key+'</code></td><td class="'+sc+'">'+st+'</td><td>'+(k.machine_id||'-')+'</td><td>'+(k.created_at||'-')+'</td><td>'+(k.activated_at||'-')+'</td><td>'+cb+' <button class="btn-delete" onclick="doDelete(\''+k.license_key+'\')">删除</button></td></tr>'});tb.innerHTML=h})}
function doGenerate(){var c=parseInt(document.getElementById('genCount').value)||1;fetch('/api/generate',{method:'POST',headers:authHeaders(),body:JSON.stringify({count:c})}).then(function(r){return r.json()}).then(function(d){if(d.ok){showToast('已生成 '+d.keys.length+' 个授权码');loadKeys()}})}
function doDelete(k){if(!confirm('确定删除授权码 '+k+'？'))return;fetch('/api/keys/'+k,{method:'DELETE',headers:authHeaders()}).then(function(r){return r.json()}).then(function(d){if(d.ok){showToast('已删除');loadKeys()}})}
function copyKey(k){navigator.clipboard.writeText(k).then(function(){showToast('已复制: '+k)})}
function doExport(){fetch('/api/keys',{headers:authHeaders()}).then(function(r){return r.json()}).then(function(d){if(!d.ok)return;var t='授权码\t状态\t机器码\t创建时间\t激活时间\n';d.keys.forEach(function(k){t+=k.license_key+'\t'+(k.machine_id?'已激活':'未使用')+'\t'+(k.machine_id||'-')+'\t'+(k.created_at||'-')+'\t'+(k.activated_at||'-')+'\n'});var b=new Blob([t],{type:'text/plain;charset=utf-8'});var a=document.createElement('a');a.href=URL.createObjectURL(b);a.download='license_keys_'+new Date().toISOString().slice(0,10)+'.txt';a.click()})}
</script>
</body>
</html>"""
PYEOF
```

**第 3 段：**
```bash
cat >> main.py << 'PYEOF'

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


@app.get("/admin", response_class=HTMLResponse)
def admin_page():
    return HTMLResponse(content=ADMIN_HTML)


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
    key = req.key.strip().upper()
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM license_keys WHERE license_key = ?", (key,)).fetchone()
        if not row:
            return {"ok": False, "msg": "授权码不存在"}
        if row["machine_id"] is None:
            conn.execute("UPDATE license_keys SET machine_id = ?, activated_at = CURRENT_TIMESTAMP WHERE license_key = ?", (req.machine_id, key))
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
        rows = conn.execute("SELECT license_key, machine_id, created_at, activated_at FROM license_keys ORDER BY id DESC").fetchall()
    finally:
        conn.close()
    return {"ok": True, "keys": [dict(r) for r in rows]}
PYEOF
```

### 第 4 步：重新构建并启动

```bash
cd /opt/license-server
export ADMIN_PASSWORD="你的密码"
docker compose up -d --build
```

### 第 5 步：验证

浏览器打开：

```
http://49.51.75.21:8080/admin
```

输入管理密码登录，看到授权码管理页面即为成功。
