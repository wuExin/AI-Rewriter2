在当前项目的基础上，增加一机一码授权机制。
## 1. 功能需求
1. 应用启动时，检查是否存在授权码。
2. 如果存在授权码，直接进入主界面。
3. 如果不存在授权码，弹出授权码输入框。
4. 输入授权码后，应用会验证授权码是否正确。
5. 如果正确，授权码会被写入本地文件，应用会进入主界面。
6. 如果错误，应用会提示用户重新输入。

## 2. 一机一码授权机制

### 2.1 总体流程

```
应用启动
    │
    ▼
MainWindow.__init__()
    │
    ▼
_check_license()
    ├── 读取 .license 文件
    ├── _get_machine_id()  → 16 位 hex 机器指纹
    ├── _verify_license(key, machine_id)  → POST 服务器
    │      ok=True  ──────────────► 进入主界面
    │      ok=False ──┐
    │                 ▼
    │           _show_license_dialog(machine_id)
    │              ├── 弹窗输入授权码 (最多 3 次)
    │              ├── 成功 → 写入 .license → 进入主界面
    │              └── 失败 → sys.exit(0)
```

### 2.2 机器码生成 `_get_machine_id()`

**优先路径：Windows 主板序列号**

```python
result = subprocess.run(
    ['wmic', 'baseboard', 'get', 'serialnumber'],
    capture_output=True, text=True, timeout=5,
    creationflags=CREATE_NO_WINDOW   # 隐藏黑窗
)
sn = result.stdout.split('\n')[1].strip()

if sn and sn != 'To be filled by O.E.M.' and len(sn) > 3:
    machine_id = hashlib.md5(sn.encode()).hexdigest()[:16]
```

**降级路径：网卡 MAC 地址**

当 `wmic` 失败、超时、或返回 OEM 占位符时：

```python
mac = uuid.getnode()
machine_id = hashlib.md5(str(mac).encode()).hexdigest()[:16]
```

> 结果：`machine_id` 始终是 16 位十六进制字符串。
> 缺陷：MAC 在虚拟机/Docker/网卡更换后会变；主板换主板后授权也失效。

### 2.3 授权码格式

```
XXXX-XXXX-XXXX-XXXX
```
4 组 × 4 字符，总长 19。客户端做 `.strip().upper()` 归一化后再发送。

### 2.4 License 文件存储 `_get_license_path()`

```python
if getattr(sys, 'frozen', False):
    base = os.path.dirname(sys.executable)  # exe 所在目录
else:
    base = os.path.dirname(os.path.abspath(__file__))

return os.path.join(base, '.license')
```

**明文存储**授权码，便于跨启动复用。

### 2.5 在线验证 `_verify_license(key, machine_id)`

```python
POST http://47.103.28.238:8080/api/verify
Content-Type: application/json
Timeout: 10s

{"key": "XXXX-XXXX-XXXX-XXXX", "machine_id": "a1b2c3d4e5f6a7b8"}
```

服务端返回：

```json
{"ok": true,  "msg": ""}
{"ok": false, "msg": "授权码与机器不匹配"}
```

客户端逻辑：

```python
try:
    r = requests.post(URL, json=payload, timeout=10)
    data = r.json()
    return data.get('ok', False), data.get('msg', '')
except Exception:
    return False, '网络连接失败，请检查网络后重试'
```

### 2.6 关键设计取舍

| 设计 | 优点 | 缺点 |
|---|---|---|
| 服务端集中验证 | 撤销/封号方便 | 必须联网，断网即不可用 |
| 客户端无加密签名 | 实现简单 | 易被中间人/mock 拦截 |
| 主板 SN + MAC 双兜底 | 兼容性强 | 虚拟化环境授权易漂移 |
| `.license` 明文 | 跨启动免输入 | 复制文件即可在同一机器换用户 |
| 启动即校验，失败 `sys.exit` | 防绕过 | 启动慢，无离线宽限期 |