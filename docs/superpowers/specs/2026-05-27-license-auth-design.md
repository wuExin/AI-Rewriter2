# 一机一码授权机制设计

## 概述

在现有 AI 文章改写工具中增加一机一码授权机制。应用启动时校验授权码，未授权则弹窗输入，验证通过后写入本地 `.license` 文件，后续启动自动验证。

## 架构

新增 `src/license.py` 模块，包含所有授权相关逻辑。在 `src/gui.py` 的 `App.__init__()` 中调用入口方法。

### 模块结构

```
src/license.py
├── _get_machine_id()        # 机器码生成（16位hex）
├── _get_license_path()      # .license 文件路径
├── _verify_license(key, machine_id)  # 在线验证（POST）
├── _show_license_dialog(machine_id)  # 授权弹窗（CTkToplevel）
└── check_license()          # 入口方法，供 App.__init__ 调用
```

## 详细设计

### 1. 机器码生成 `_get_machine_id()`

**优先路径：Windows 主板序列号**

```python
result = subprocess.run(
    ['wmic', 'baseboard', 'get', 'serialnumber'],
    capture_output=True, text=True, timeout=5,
    creationflags=subprocess.CREATE_NO_WINDOW
)
sn = result.stdout.split('\n')[1].strip()
if sn and sn != 'To be filled by O.E.M.' and len(sn) > 3:
    return hashlib.md5(sn.encode()).hexdigest()[:16]
```

**降级路径：网卡 MAC 地址**

```python
mac = uuid.getnode()
return hashlib.md5(str(mac).encode()).hexdigest()[:16]
```

结果始终是 16 位十六进制字符串。

### 2. License 文件路径 `_get_license_path()`

```python
if getattr(sys, 'frozen', False):
    base = os.path.dirname(sys.executable)
else:
    base = os.path.dirname(os.path.abspath(__file__))
return os.path.join(base, '.license')
```

明文存储授权码，跨启动复用。

### 3. 在线验证 `_verify_license(key, machine_id)`

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

### 4. 授权弹窗 `_show_license_dialog(machine_id)`

- customTkinter `CTkToplevel` 模态弹窗
- 显示当前机器码（只读，方便用户报给管理员）
- 授权码输入框（格式 XXXX-XXXX-XXXX-XXXX）
- 客户端对输入做 `.strip().upper()` 归一化
- 验证按钮：POST 服务器校验
- 最多 3 次验证机会，每次失败显示错误信息
- 成功：写入 `.license` 文件，关闭弹窗
- 3 次均失败：`sys.exit(0)` 终止应用

### 5. 入口方法 `check_license()`

```
读取 .license 文件
  ├── 文件不存在 → 弹出授权弹窗
  └── 文件存在
       ├── 取机器码
       ├── 在线验证已存授权码
       │    ├── ok=True → 返回（进入主界面）
       │    └── ok=False → 弹出授权弹窗
       └── 弹窗成功 → 写入 .license → 返回
           弹窗失败 → sys.exit(0)
```

## 集成点

`src/gui.py` 的 `App.__init__()` 中，在 `super().__init__()` 之后、`_build_ui()` 之前插入：

```python
from .license import check_license
check_license(self)
```

`check_license` 接收 `App` 实例作为 parent 窗口参数，用于创建 `CTkToplevel` 弹窗。

## 依赖

- `requests`：用于 HTTP POST 验证。需确认已安装或添加到依赖。
- 标准库：`hashlib`, `uuid`, `subprocess`, `os`, `sys`

## 文件变更清单

| 文件 | 操作 |
|------|------|
| `src/license.py` | 新增：授权模块 |
| `src/gui.py` | 修改：`__init__` 中调用 `check_license(self)` |
