# RPD - Requirements & Product Design

## 1. 项目概述

**ytdlp_bot** 是一个 Telegram 视频下载机器人。用户在聊天中发送包含视频链接的消息，机器人自动识别链接、下载视频并将视频文件回传给用户。

### 1.1 核心目标

- 零门槛使用：用户只需发送链接，无需任何命令
- 多平台支持：YouTube、Bilibili、X (Twitter)
- 稳定可靠：完善的错误处理与文件大小管控
- 灵活部署：支持代理/直连，Docker 一键部署

---

## 2. 功能需求

### 2.1 链接识别

机器人监听所有收到的文本消息，使用正则表达式匹配以下平台的视频链接：

| 平台 | 匹配模式 | 示例 |
|------|---------|------|
| YouTube | `youtube.com/watch?v=`, `youtu.be/`, `youtube.com/shorts/` | `https://www.youtube.com/watch?v=dQw4w9WgXcQ` |
| Bilibili | `bilibili.com/video/`, `b23.tv/` | `https://www.bilibili.com/video/BV1xx411c7mD` |
| X (Twitter) | `twitter.com/*/status/`, `x.com/*/status/` | `https://x.com/user/status/123456789` |

- 每条消息中可能包含 **多个链接**，需全部识别并逐一处理
- 链接可能嵌在文字中间，正则需支持从文本中提取
- 忽略非视频链接（如频道首页、用户主页等）

### 2.2 视频下载

使用 yt-dlp 作为下载后端：

1. **格式选择策略**：
   - 优先选择 **音视频合并后不超过 50MB** 的最佳画质
   - yt-dlp format 选择逻辑：`(bv*+ba/b)[filesize<50M]` 并回退到 `(bv*+ba/b)` 再做后处理
   - 优先 mp4 容器格式（Telegram 原生支持预览）

2. **下载目录**：
   - 默认 `/tmp/ytdlp_bot_downloads/`
   - 可通过 `DOWNLOAD_DIR` 环境变量自定义

3. **Cookie / Header**：
   - 暂不实现，后续可扩展

### 2.3 文件大小管控

由于官方 Telegram Bot API 限制 50MB 上传，本项目已支持 **Local Bot API Server** 来突破限制，处理流程：

```
下载完成
  │
  ├─ ≤ MAX_FILE_SIZE (默认2GB) → 直接发送
  │
  └─ > MAX_FILE_SIZE → 通知用户"视频过大，无法发送"
```

### 2.4 用户交互

#### 发送视频时
1. 用户发送包含链接的消息
2. 机器人回复「⏳ 正在下载...」状态消息
3. 下载完成后更新为「📤 正在上传...」
4. 发送视频文件，删除状态消息
5. 清理本地临时文件

#### 命令
| 命令 | 说明 |
|------|------|
| `/start` | 欢迎消息 + 使用说明 |
| `/help` | 使用帮助，列出支持的平台 |

#### 错误处理
- 链接无法解析 → 「❌ 无法识别该链接」
- 下载失败 → 「❌ 下载失败：{原因}」
- 文件过大 → 「❌ 视频过大（超过 {N}MB），无法发送」
- 网络错误 → 「❌ 网络错误，请稍后重试」

---

## 3. 技术设计

### 3.1 技术栈

| 组件 | 选型 | 说明 |
|------|------|------|
| 语言 | Python 3.12+ | 主力开发语言 |
| 包管理 | uv | 高性能 Python 包管理 |
| Bot 框架 | pyTelegramBotAPI | 成熟的 Telegram Bot SDK |
| 下载器 | yt-dlp | 多平台视频下载 |
| 视频处理 | ffmpeg | 压缩、转码 |
| 配置管理 | pydantic-settings | 类型安全的环境变量管理 |
| 部署 | Docker + Compose | 容器化一键部署 |

### 3.2 项目结构

```
ytdlp_bot/
├── src/
│   └── ytdlp_bot/
│       ├── __init__.py
│       ├── main.py           # 入口：初始化配置 → 启动 bot
│       ├── config.py         # Settings 类，pydantic-settings
│       ├── bot.py            # Bot 实例化、消息 handler 注册
│       ├── downloader.py     # yt-dlp 封装
│       └── patterns.py       # 正则表达式定义与链接提取
├── .env.example
├── .gitignore
├── pyproject.toml
├── Dockerfile
└── docker-compose.yml
```

### 3.3 模块详细设计

#### `config.py` - 配置管理

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # 必填
    TELEGRAM_BOT_TOKEN: str

    # 可选 - 代理与 API
    TELEGRAM_API_URL: str | None = None
    PROXY_URL: str | None = None  # http://host:port 或 socks5://host:port

    # 可选 - 下载
    DOWNLOAD_DIR: str = "/tmp/ytdlp_bot_downloads"
    MAX_FILE_SIZE: int = 2000 * 1024 * 1024  # 默认 2000MB

    # 可选 - 日志
    LOG_LEVEL: str = "INFO"
```

#### `patterns.py` - 链接匹配

为每个平台定义正则表达式，暴露 `extract_urls(text) -> list[tuple[str, str]]` 方法，返回 `(url, platform)` 列表。

```python
PATTERNS = {
    "youtube": re.compile(
        r'https?://(?:www\.)?(?:youtube\.com/(?:watch\?v=|shorts/)|youtu\.be/)[\w\-]+'
    ),
    "bilibili": re.compile(
        r'https?://(?:www\.)?(?:bilibili\.com/video/[\w]+|b23\.tv/[\w]+)'
    ),
    "twitter": re.compile(
        r'https?://(?:www\.)?(?:twitter|x)\.com/\w+/status/\d+'
    ),
}
```

#### `downloader.py` - 下载逻辑

封装 yt-dlp 的下载过程：

```python
class Downloader:
    def __init__(self, settings: Settings): ...

    def download(self, url: str) -> DownloadResult:
        """
        下载视频，返回文件路径和元信息。
        yt-dlp 配置要点：
        - format: 优先选不超过 MAX_FILE_SIZE 的最佳画质
        - proxy: 从 settings.PROXY_URL 读取
        - outtmpl: 输出到 DOWNLOAD_DIR
        - merge_output_format: mp4
        """
        ...
```

`DownloadResult` 数据模型：
```python
@dataclass
class DownloadResult:
    file_path: str
    title: str
    duration: int | None  # 秒
    file_size: int  # 字节
```

#### `bot.py` - Bot 主逻辑

```python
class VideoBot:
    def __init__(self, settings: Settings): ...

    def _setup_handlers(self):
        @self.bot.message_handler(commands=['start', 'help'])
        def handle_command(message): ...

        @self.bot.message_handler(func=lambda m: m.text and extract_urls(m.text))
        def handle_url(message): ...

    def _process_video(self, message, url, platform):
        """
        完整处理流程：
        1. 发送"下载中"状态
        2. 调用 downloader.download()
        3. 检查文件大小是否超过限制
        4. 发送视频到 Telegram
        5. 清理临时文件
        6. 错误处理
        """
        ...

    def run(self):
        self.bot.infinity_polling(...)
```

#### `main.py` - 入口

```python
def main():
    settings = Settings()
    logging.basicConfig(level=settings.LOG_LEVEL)
    bot = VideoBot(settings)
    bot.run()

if __name__ == "__main__":
    main()
```

### 3.4 代理设计

代理为 **可选配置**，通过 `PROXY_URL` 环境变量设置：

| 场景 | 处理 |
|------|------|
| 未设置 `PROXY_URL` | 直连 Telegram API 和视频源 |
| 设置 HTTP 代理 | `http://host:port` 同时用于 telebot 和 yt-dlp |
| 设置 SOCKS5 代理 | `socks5://host:port` 同时用于 telebot 和 yt-dlp |

**Telegram Bot (pyTelegramBotAPI) 代理配置**：
```python
from telebot import apihelper
if settings.PROXY_URL:
    apihelper.proxy = {'https': settings.PROXY_URL}
```

**yt-dlp 代理配置**：
```python
ydl_opts = {
    'proxy': settings.PROXY_URL,  # yt-dlp 原生支持 http/socks5
    ...
}
```

### 3.5 Docker 部署

#### Dockerfile

- 基础镜像：`python:3.12-slim`
- 安装系统依赖：`ffmpeg`
- 使用 uv 安装 Python 依赖
- 非 root 用户运行

#### docker-compose.yml

```yaml
services:
  bot:
    build: .
    restart: unless-stopped
    env_file: .env
    volumes:
      - downloads:/tmp/ytdlp_bot_downloads
volumes:
  downloads:
```

---

## 4. 环境变量

| 变量名 | 必填 | 默认值 | 说明 |
|--------|------|--------|------|
| `TELEGRAM_BOT_TOKEN` | ✅ | - | Telegram Bot Token (从 @BotFather 获取) |
| `TELEGRAM_API_URL` | ❌ | `None` | 自定义 Telegram Bot API Server 的基础 URL，如 `http://api-server:8081` |
| `PROXY_URL` | ❌ | `None` | 代理地址，如 `http://host:port` 或 `socks5://host:port` |
| `DOWNLOAD_DIR` | ❌ | `/tmp/ytdlp_bot_downloads` | 临时下载目录 |
| `MAX_FILE_SIZE` | ❌ | `2097152000` (2000MB) | Telegram 上传文件大小限制 (字节) |
| `LOG_LEVEL` | ❌ | `INFO` | 日志级别 |

---

## 5. 处理流程

### 5.1 主流程时序

```
User                Bot                 Downloader
 │                   │                      │
 │  发送含链接消息    │                      │
 │ ─────────────────>│                      │
 │                   │  正则提取 URL         │
 │                   │──┐                   │
 │                   │<─┘                   │
 │  「⏳ 正在下载」   │                      │
 │ <─────────────────│                      │
 │                   │  download(url)       │
 │                   │ ────────────────────>│
 │                   │  DownloadResult      │
 │                   │ <────────────────────│
 │                   │                      │
 │  「📤 正在上传」   │  if <= MAX_FILE_SIZE:│
 │ <─────────────────│                      │
 │                   │                      │
 │  发送视频文件      │                      │
 │ <─────────────────│                      │
 │                   │  清理临时文件         │
 │                   │──┐                   │
 │                   │<─┘                   │
```

### 5.2 错误处理流程

- 所有异常在 `_process_video` 层统一捕获
- 向用户发送友好的错误消息
- 记录详细错误日志（包含 traceback）
- **无论成功失败，都必须清理临时文件**

---

## 6. 后续扩展（不在当前版本实现）

- [ ] 支持更多平台（Instagram、TikTok、Reddit 等）
- [ ] Cookie 支持（登录态下载会员/私有视频）
- [ ] 下载队列（避免并发过多导致资源耗尽）
- [ ] 用户白名单/黑名单
- [ ] 下载进度回调更新消息
- [ ] 音频提取模式（`/audio` 命令）
- [ ] Webhook 模式替代 polling