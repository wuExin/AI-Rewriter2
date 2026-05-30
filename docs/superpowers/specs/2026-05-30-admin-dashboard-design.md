# 授权码管理后台设计

## 目标

在现有 FastAPI 授权服务中内嵌一个管理网页，用于查看、生成、删除、复制授权码。

## 方案

内嵌 HTML 页面，零额外依赖。一个 HTML 文件包含所有前端代码（HTML + CSS + JS），由 FastAPI 直接返回。

## 页面结构

### 登录区

- 密码输入框 + 登录按钮
- 登录成功后隐藏登录区，显示管理区
- 密码存储在 sessionStorage，刷新页面不需要重新登录

### 管理区（登录后显示）

**操作栏**：
- 生成授权码：输入数量（1-100）+ 生成按钮，生成后自动刷新列表

**授权码表格**：

| 列 | 说明 |
|----|------|
| 授权码 | XXXX-XXXX-XXXX-XXXX 格式 |
| 状态 | 已激活 / 未使用 |
| 机器码 | 绑定的机器码，未激活显示 "-" |
| 创建时间 | 创建日期 |
| 激活时间 | 激活日期，未激活显示 "-" |
| 操作 | 复制按钮（未使用的码）、删除按钮 |

**导出**：
- 底部"导出全部"按钮，导出为纯文本格式（授权码 + 状态）

## 前端技术

- 纯 HTML + CSS + JavaScript
- 无框架、无构建步骤
- 响应式布局，手机也能看
- 风格：简洁白底表格

## 后端改动

在 `server/main.py` 中新增：

| 端点 | 方法 | 说明 |
|------|------|------|
| `/admin` | GET | 返回管理页面 HTML |
| `/api/login` | POST | 验证密码，返回成功/失败 |
| `/api/keys/{key}` | DELETE | 删除指定授权码（需密码） |

已有 API 不变：
- `POST /api/verify` — 验证授权码
- `POST /api/generate` — 生成授权码
- `GET /api/keys` — 查看所有授权码

## 文件改动

| 文件 | 改动 |
|------|------|
| `server/main.py` | 新增 `/admin`、`/api/login`、`DELETE /api/keys/{key}` 三个端点 |
| `server/admin.html`（新增） | 管理页面 HTML |

## 鉴权方式

所有管理 API 通过 `Authorization: Bearer <password>` 鉴权，与现有 `/api/generate` 和 `/api/keys` 保持一致。前端登录成功后将密码存入 sessionStorage，每次请求携带。
