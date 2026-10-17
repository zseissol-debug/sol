# 自媒体工作台 · 代码

复刻 Park 的「帕克动手」工作台。当前做了：**进项 · AI 日报**、**进项 · 拆解报告**（含「拆解」任务）、**选题池**，以及全部页面的框架。其余页面是占位，写明了原版有什么、第几期做。

## 启动

```bash
scripts/setup.sh      # 第一次：装后端、前端、两个开源引擎（固定版本，见 scripts/engines.lock）
scripts/start.sh      # 启动，然后打开 http://127.0.0.1:8000
```

只监听本机 `127.0.0.1`，没有登录。数据都在 `app/data/`。

## 现在能做什么

| 功能 | 不需要配置就能用 | 需要你配置 |
|---|---|---|
| 进项 · AI 日报 | 点「同步 Park 公开日报」，读 Park 公开的最近约 30 期；每条可「入选题池」 | 「生成今日日报」：要给日报引擎配一个 AI（见下） |
| 进项 · 拆解报告 | 点「导入 Park 公开拆解库」，看他拆好的 50 份；可入选题池、归档 | 「拆解」自己的链接：抖音 cookies + 一个 AI + 本地转写（见下） |
| 加工中 · 选题池 | 入池的条目都在这里，可改阶段、不做了、手动加 | — |

页面上的「检查日报引擎」「检查拆解环境」会逐项告诉你缺什么。

### 想自己生成日报

```bash
cp engines/daily-newsletter/.env.example engines/daily-newsletter/.env
# 编辑 .env，至少填一个 AI：PARKIO_DEEPSEEK_KEY=…，或 PARKIO_LLM_PROVIDER=claude / codex（命令要已登录）
```

没有登录态的来源（X、抖音）会被跳过，日报照样出，只是内容少一些。一次生成要十几分钟到半小时。

### 想拆自己的链接

1. `scripts/setup.sh --full`：装本地转写（Apple 芯片用 mlx-whisper，体积大，第一次用还会下载模型）。
2. **抖音 cookies**：自己登录 douyin.com，导出 cookies，存成 `~/.douyin-teardown/cookies.json`（格式见 [cookies.json.example](https://github.com/zinan92/douyin-teardown/blob/main/cookies.json.example)），再 `chmod 600`。工作台不替你登录、不读浏览器。
3. **AI**：在 `app/.env` 写 `TEARDOWN_AI=deepseek` 加 `TEARDOWN_DEEPSEEK_KEY=…`，或 `TEARDOWN_AI=anthropic` 加 `ANTHROPIC_API_KEY=…`，或用已登录的 `claude` / `codex` 命令。

拆解会用你的抖音登录去拉作者最近的作品，所以：**同时最多排 3 条**；抖音弹验证页就会停，不绕过。

## 目录

```
backend/studio/      接口、数据模型、解析器、两个引擎的适配层
backend/tests/       45 个测试（用真实的 Park 公开数据当样本）
frontend/src/        React 页面
scripts/             setup.sh、start.sh、engines.lock
engines/             日报引擎（setup 时克隆，固定版本）
data/                运行数据（不进 git）
```

开发：`cd backend && ../.venv/bin/python -m pytest`；前端热更新 `cd frontend && npm run dev`（5173，代理到 8000）。

## 许可与数据

- 引用的两个引擎（douyin-teardown、daily-newsletter）都是 MIT，按固定 commit 安装，没有复制进本项目。
- 「Park 公开库」的日报和拆解报告来自作者公开的 RSS，页面上都标了来源。**原话版权归原作者，仅供你本地学习演示，不要带着它们对外发布。**
- 尚未使用任何没有许可证的代码（park-video-v2、content-ops 等只当参考）。
