# Epic Freebies Helper

[English](README.en.md)

自动登录 Epic Games Store、检查当前周免并完成领取。项目可运行在 GitHub
Actions、本地环境或 Docker 中，并使用支持图片输入的 LLM 处理必要的 hCaptcha
挑战。

本项目不绑定具体模型厂商或中转服务。`LLM_PROVIDER` 表示请求协议，而不是服务商品牌。

## 功能

- 自动登录、查询周免、检查订单历史并领取尚未拥有的免费游戏
- GitHub Actions 每 3 天自动运行，也支持手动触发
- 支持 Camoufox，并在不可用时回退到 Playwright Firefox
- 支持四种原生 LLM 请求协议
- 上传日志、截图和挑战运行产物，便于排查失败

## 快速开始：GitHub Actions

1. Fork 本仓库。
2. 在 Fork 的 `Actions` 页面启用 `Epic Freebies Helper (Scheduled)`。
3. 打开 `Settings` → `Secrets and variables` → `Actions`。
4. 创建下列 Secrets：

| 名称 | 示例 | 说明 |
| --- | --- | --- |
| `EPIC_EMAIL` | `you@example.com` | Epic 账号邮箱 |
| `EPIC_PASSWORD` | `your-password` | Epic 账号密码 |
| `LLM_PROVIDER` | `openai` | 请求协议，默认 `openai` |
| `LLM_API_KEY` | `sk-...` | 所选服务的 API Key |
| `LLM_BASE_URL` | `https://llm.example.com/v1` | 自定义 API 根地址 |
| `LLM_MODEL` | `your-vision-model` | 必须支持图片输入 |

`LLM_PROVIDER`、`LLM_BASE_URL`、`LLM_MODEL` 也可以放在 GitHub Actions
Variables 中；工作流优先读取 Variable，并兼容同名 Secret。API Key 应始终放在 Secret。

如果你原来使用 `OPENAI_API_KEY`、`OPENAI_BASE_URL`、`OPENAI_MODEL`，迁移时只需将
名称改为 `LLM_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL`。`EPIC_EMAIL`、
`EPIC_PASSWORD` 和 `LLM_PROVIDER=openai` 不变。

完成配置后，在 Actions 页面手动运行一次工作流。之后 GitHub 会按每 3 天一次的计划执行。

## LLM 协议

| `LLM_PROVIDER` | 请求接口 | 缺少版本段时自动补全 |
| --- | --- | --- |
| `openai` | `POST /v1/chat/completions` | `/v1` |
| `openai-responses` | `POST /v1/responses` | `/v1` |
| `gemini` | `POST /v1beta/models/{model}:generateContent` | `/v1beta` |
| `claude` | `POST /v1/messages` | `/v1` |

### Base URL 规则

- 你现在使用的 `https://你的地址/v1` 是正确的，继续保留 `/v1` 即可。
- 如果填写 `https://你的地址`，程序会按协议自动补上 `/v1`；Gemini 会补
  `/v1beta`。
- 已经包含版本段时不会重复添加，因此不会出现 `/v1/v1`。
- `LLM_BASE_URL` 填 API 根地址即可，不需要再拼
  `/chat/completions`、`/responses`、`/messages` 或 `:generateContent`。
- 使用官方 API 时可以留空 `LLM_BASE_URL`，程序会使用相应官方地址。
- 兼容服务必须真正实现所选协议；地址看起来像 OpenAI 并不代表它支持 Responses、
  Gemini 或 Claude 请求体。

## 本地运行

要求 Python 3.12 或 3.13，以及 [uv](https://docs.astral.sh/uv/)。

```powershell
git clone https://github.com/TheWiseWolfHolo/epic-freebies-helper.git
cd epic-freebies-helper
Copy-Item .env.example .env
uv sync
uv run camoufox fetch
$env:ENABLE_APSCHEDULER = "false"
uv run app/deploy.py
```

编辑 `.env` 并填写 Epic 与 LLM 配置。密码或 Key 包含 `$`、`\`、`#` 或反引号时，
在 `.env` 中用单引号包裹；GitHub Actions Secrets 不受此影响。

## Docker

复制 Docker 环境模板、填写配置后执行：

```powershell
Set-Location docker
Copy-Item .env.example .env
# 编辑 .env
docker compose up -d
docker compose logs -f
```

Compose 默认使用本项目发布到 GHCR 的镜像。若当前版本尚未发布镜像，可从仓库根目录
自行构建：

```powershell
docker build -f docker/Dockerfile -t epic-freebies-helper .
```

## 注意事项

- Epic 的登录风控和验证码会随运行地区、公共 IP 与账号状态波动，自动化不保证每次成功。
- 账号启用 2FA 时，自动登录可能停在二次验证步骤。请根据自己的安全需求决定是否使用
  独立账号；不要为了自动化降低主账号安全性。
- 工作流成功但没有确认邮件时，游戏可能已存在于库中。以日志中的订单历史和领取结果为准。
- 私有 Fork 的 Actions 页面无法由维护者访问；报告问题时请附上本次运行生成的日志、
  截图或 artifact，并先移除敏感信息。
- 请遵守 Epic Games、模型服务商及 GitHub 的使用条款，并自行承担账号与自动化风险。

更多配置与协议排查见 [高级说明](docs/advanced.md)，历史变更见
[维护日志](docs/maintenance-log.md)。

## 项目来源

本项目基于开源社区的 Epic 自动领取实践持续维护，主要参考：

- [Ronchy2000/epic-freebies-helper](https://github.com/Ronchy2000/epic-freebies-helper)
- [QIN2DIM/epic-awesome-gamer](https://github.com/QIN2DIM/epic-awesome-gamer)
- [10000ge10000/epic-kiosk](https://github.com/10000ge10000/epic-kiosk)

项目遵循 [GNU General Public License v3.0](LICENSE)。
