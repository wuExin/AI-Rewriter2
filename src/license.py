"""
客户端授权验证模块
- 机器指纹采集
- 在线密钥验证
- 授权对话框
"""
import hashlib
import os
import subprocess
import sys
import uuid

import customtkinter as ctk
import requests

SERVER_URL = "http://47.103.28.238:8080"


# ─── 机器指纹 ───────────────────────────────────────────────

def _get_machine_id() -> str:
    """生成 16 位十六进制机器指纹。

    优先使用 Windows 主板序列号，失败则回退到 MAC 地址。
    """
    # 优先：Windows 主板序列号
    try:
        kwargs = dict(
            capture_output=True,
            text=True,
            timeout=5,
        )
        if sys.platform == "win32":
            kwargs["creationflags"] = 0x08000000  # CREATE_NO_WINDOW

        result = subprocess.run(
            ["wmic", "baseboard", "get", "serialnumber"],
            **kwargs,
        )
        lines = [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]
        if len(lines) >= 2:
            sn = lines[1]
            invalid = {"", "To be filled by O.E.M.", "Default string", "None"}
            if sn not in invalid and len(sn) > 3:
                return hashlib.md5(sn.encode()).hexdigest()[:16]
    except Exception:
        pass

    # 回退：MAC 地址
    mac = uuid.getnode()
    return hashlib.md5(str(mac).encode()).hexdigest()[:16]


# ─── 许可证文件路径 ──────────────────────────────────────────

def _get_license_path() -> str:
    """返回 .license 文件路径（与可执行文件或本模块同目录）。"""
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, '.license')


# ─── 在线验证 ────────────────────────────────────────────────

def _verify_license(key: str, machine_id: str) -> tuple:
    """在线验证授权密钥。

    Returns:
        (ok: bool, msg: str)
    """
    try:
        resp = requests.post(
            f"{SERVER_URL}/api/verify",
            json={"key": key.strip().upper(), "machine_id": machine_id},
            timeout=10,
        )
        data = resp.json()
        return (data.get('ok', False), data.get('msg', ''))
    except Exception:
        return (False, '网络连接失败，请检查网络后重试')


# ─── 授权对话框 ──────────────────────────────────────────────

def _show_license_dialog(parent, machine_id: str):
    """弹出模态授权验证对话框。最多允许 3 次尝试，全部失败则退出。"""

    dialog = ctk.CTkToplevel(parent)
    dialog.title("授权验证")
    dialog.geometry("450x320")
    dialog.resizable(False, False)
    dialog.transient(parent)

    # 居中于父窗口
    dialog.update_idletasks()
    pw = parent.winfo_width()
    ph = parent.winfo_height()
    px = parent.winfo_x()
    py = parent.winfo_y()
    dw = dialog.winfo_width()
    dh = dialog.winfo_height()
    x = px + (pw - dw) // 2
    y = py + (ph - dh) // 2
    dialog.geometry(f"+{x}+{y}")

    # 关闭按钮直接退出
    dialog.protocol("WM_DELETE_WINDOW", lambda: sys.exit(0))

    attempts = {"count": 0}

    # ── 控件 ──

    ctk.CTkLabel(
        dialog,
        text="请输入授权密钥以激活软件",
        font=ctk.CTkFont(size=16, weight="bold"),
    ).pack(pady=(25, 10))

    # 机器码
    code_frame = ctk.CTkFrame(dialog)
    code_frame.pack(fill="x", padx=30, pady=(0, 5))

    ctk.CTkLabel(code_frame, text="机器码：", font=ctk.CTkFont(size=12)).pack(
        side="left", padx=(10, 0), pady=8
    )

    machine_label = ctk.CTkLabel(
        code_frame,
        text=machine_id,
        font=ctk.CTkFont(size=12),
        text_color="gray",
    )
    machine_label.pack(side="left", padx=5, pady=8)

    # 密钥输入
    key_entry = ctk.CTkEntry(
        dialog,
        placeholder_text="XXXX-XXXX-XXXX-XXXX",
        width=380,
        font=ctk.CTkFont(size=14),
    )
    key_entry.pack(pady=10)

    # 状态标签
    status_label = ctk.CTkLabel(
        dialog,
        text="",
        text_color="red",
        font=ctk.CTkFont(size=12),
    )
    status_label.pack(pady=5)

    # ── 验证逻辑 ──

    def do_verify(_event=None):
        key = key_entry.get().strip().upper()
        if not key:
            status_label.configure(text="请输入授权密钥")
            return

        ok, msg = _verify_license(key, machine_id)
        if ok:
            # 写入 .license 文件
            license_path = _get_license_path()
            with open(license_path, 'w', encoding='utf-8') as f:
                f.write(key)
            dialog.destroy()
        else:
            attempts["count"] += 1
            remaining = 3 - attempts["count"]
            if remaining <= 0:
                sys.exit(0)
            status_label.configure(
                text=f"{msg}（剩余 {remaining} 次尝试）"
            )

    key_entry.bind("<Return>", do_verify)

    verify_btn = ctk.CTkButton(
        dialog,
        text="验 证",
        width=200,
        command=do_verify,
    )
    verify_btn.pack(pady=10)

    dialog.grab_set()
    parent.wait_window(dialog)


# ─── 入口函数 ────────────────────────────────────────────────

def check_license(parent):
    """授权验证入口，供 App.__init__ 调用。

    1. 采集机器指纹
    2. 如已有 .license 文件则尝试在线验证
    3. 验证失败或无文件则弹出授权对话框
    """
    machine_id = _get_machine_id()
    license_path = _get_license_path()

    # 尝试读取已保存的密钥
    if os.path.isfile(license_path):
        try:
            with open(license_path, 'r', encoding='utf-8') as f:
                saved_key = f.read().strip()
            if saved_key:
                ok, _ = _verify_license(saved_key, machine_id)
                if ok:
                    return
        except Exception:
            pass

    # 需要重新授权
    _show_license_dialog(parent, machine_id)
