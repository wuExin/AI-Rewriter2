# 授权验证后端部署到腾讯云

## 目标

将授权验证服务（`server/`）部署到腾讯云服务器（49.51.75.21），使多台电脑上的桌面客户端能共享云端授权验证。客户端无需其他改动，仅修改 `SERVER_URL`。

## 架构

```
桌面客户端 (多台) ──HTTP──> 腾讯云 49.51.75.21:8080 ──> FastAPI 授权服务 ──> SQLite
```

## 改动范围

### 新增文件

| 文件 | 说明 |
|------|------|
| `server/Dockerfile` | Docker 镜像构建，基于 python:3.11-slim |
| `server/docker-compose.yml` | 编排配置，端口映射、数据卷、环境变量 |

### 修改文件

| 文件 | 改动 |
|------|------|
| `src/license.py` | `SERVER_URL` 从 `http://127.0.0.1:8080` 改为 `http://49.51.75.21:8080` |

## Docker 部署配置

### Dockerfile

- 基础镜像：`python:3.11-slim`
- 复制 `main.py`、`db.py`、`requirements.txt` 到 `/app/`
- 安装依赖
- 数据库文件存放于 `/app/data/license.db`（通过数据卷持久化）
- 启动命令：`uvicorn main:app --host 0.0.0.0 --port 8080`

### docker-compose.yml

- 端口映射：`8080:8080`
- 环境变量：`ADMIN_PASSWORD`（管理授权码的密码，部署时设置）
- 命名卷 `license-data` 挂载到 `/app/data`，SQLite 数据持久化
- `restart: unless-stopped` 自动重启

### db.py 适配

`DB_PATH` 需要改为 `/app/data/license.db`，使数据库文件落在数据卷挂载目录内，容器重建后数据不丢失。

## 腾讯云安全组

放通 TCP 8080 端口入站规则（0.0.0.0/0），允许外网访问授权服务。

## 部署步骤（非技术用户指南）

1. **SSH 登录服务器**：腾讯云控制台 → 云服务器 → 实例 → 登录（OrcaTerm 网页终端）
2. **安装 Docker**：一条命令安装
3. **上传服务文件**：在服务器上创建目录并写入 Dockerfile、docker-compose.yml、main.py、db.py、requirements.txt
4. **启动服务**：`docker compose up -d`
5. **验证**：浏览器访问 `http://49.51.75.21:8080/docs` 看到 API 文档即为成功

## 协议

HTTP（后续可按需升级 HTTPS）。
