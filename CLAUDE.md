# CLAUDE.md - Project Intelligence

## Project Overview

**ytdlp_bot** 是一个基于 Python 的 Telegram 视频下载机器人。用户在 Telegram 中发送视频链接，机器人自动识别、下载并发送视频文件。

## Tech Stack

- **Language**: Python 3.12+
- **Package Manager**: uv
- **Telegram Bot Framework**: pyTelegramBotAPI (telebot)
- **Video Downloader**: yt-dlp
- **Video Processing**: ffmpeg (仅用于 yt-dlp 合并音视频流)
- **Configuration**: pydantic-settings + `.env` 文件
- **Deployment**: Docker + Docker Compose
- **Proxy**: 支持 HTTP / SOCKS5 代理（可选），同时作用于 Telegram Bot API 和 yt-dlp
- **Local Bot API**: 支持配置自定义 Telegram Bot API Server 以突破 50MB 上传限制

## Project Structure

```
ytdlp_bot/
├── CLAUDE.md                # 本文件 - 项目智能指南
├── docs/
│   └── RPD.md               # 需求与产品设计文档
├── src/
│   └── ytdlp_bot/
│       ├── __init__.py
│       ├── main.py           # 入口文件，启动 bot
│       ├── config.py         # pydantic-settings 配置管理
│       ├── bot.py            # Telegram bot 初始化与消息处理
│       ├── downloader.py     # yt-dlp 下载逻辑
│       └── patterns.py       # 正则匹配各平台链接
├── .env.example              # 环境变量示例
├── .env                      # 实际环境变量（不提交）
├── .gitignore
├── pyproject.toml            # uv 项目配置
├── Dockerfile
└── docker-compose.yml
```

## Key Design Decisions

### 链接识别
- 使用正则表达式匹配消息中的视频链接
- 支持平台：YouTube、Bilibili、X (Twitter)
- 每条消息可能包含多个链接，需全部识别处理

### 文件大小策略
- 由于官方 Telegram Bot API 限制 50MB 上传，本项目已重构为支持**自建 Local Bot API Server**。
- 默认 `MAX_FILE_SIZE` 为 2000MB (2GB)。
- 如果下载视频超过该限制，直接向用户返回错误提示。
- 取消了原先由于 50MB 限制而引入的视频二次压缩（ffmpeg 压缩）逻辑，以提高服务器处理效率和视频画质。

### 代理配置
- 代理是**可选**配置项，不设置则直连
- 同一代理同时用于 Telegram Bot API 请求和 yt-dlp 下载
- 支持 HTTP (`http://host:port`) 和 SOCKS5 (`socks5://host:port`) 格式
- 通过 `.env` 中的 `PROXY_URL` 配置

### 配置管理
- 使用 pydantic-settings 的 `BaseSettings` 从 `.env` 读取配置
- 必填项：`TELEGRAM_BOT_TOKEN`, `TELEGRAM_API_ID`, `TELEGRAM_API_HASH` (后两者用于 docker-compose 启动 API Server)
- 可选项：`TELEGRAM_API_URL`, `PROXY_URL`, `DOWNLOAD_DIR`, `MAX_FILE_SIZE`

## Development Commands

```bash
# 安装依赖
uv sync

# 本地运行
uv run python -m ytdlp_bot.main

# Docker 部署
docker compose up -d --build

# 查看日志
docker compose logs -f

# 停止服务
docker compose down
```

## Important Notes

- `.env` 文件包含敏感信息（Bot Token、代理地址），绝对不能提交到 git
- 下载的临时视频文件应在发送后及时清理
- yt-dlp 需要 ffmpeg 作为依赖（合并音视频流、压缩等）
- Docker 镜像中必须包含 ffmpeg
- bot 使用 polling 模式运行（非 webhook），适合在有代理的环境中使用