# GitHub Actions 配置

工作流 `epic-gamer.yml`（`Epic Freebies Helper (Scheduled)`）支持手动触发，并按每
3 天一次的计划运行。

## 必需配置

打开仓库的 `Settings` → `Secrets and variables` → `Actions`。

Secrets：

| 名称 | 说明 |
| --- | --- |
| `EPIC_EMAIL` | Epic 账号邮箱 |
| `EPIC_PASSWORD` | Epic 账号密码 |
| `LLM_API_KEY` | 所选 LLM 服务的 API Key |

Variables（也兼容同名 Secrets）：

| 名称 | 说明 |
| --- | --- |
| `LLM_PROVIDER` | `openai`、`openai-responses`、`gemini` 或 `claude` |
| `LLM_BASE_URL` | 自定义 API 根地址；官方接口可留空 |
| `LLM_MODEL` | 支持图片输入的模型名 |

工作流读取 Variable 时优先于同名 Secret。`LLM_API_KEY` 只从 Secret 读取。

## OpenAI 格式示例

```text
LLM_PROVIDER=openai
LLM_API_KEY=你的 Key
LLM_BASE_URL=https://your-provider.example/v1
LLM_MODEL=your-vision-model
```

自定义地址已经带 `/v1` 时保持原样；缺少版本段时程序会自动补 `/v1`。不要追加
`/chat/completions`。

## 其他协议

| 协议 | 自动请求路径 |
| --- | --- |
| `openai-responses` | `/v1/responses` |
| `gemini` | `/v1beta/models/{model}:generateContent` |
| `claude` | `/v1/messages` |

Gemini 的版本段是 `/v1beta`，与其他三个协议不同。

## 运行与排查

首次配置后，在 `Actions` → `Epic Freebies Helper (Scheduled)` 中手动执行一次。工作流
结束后会上传：

- `epic-runtime-*`：运行状态与挑战产物
- `epic-logs-*`：日志
- `epic-screenshots-*`：截图

GitHub 只显示实际包含文件的 artifact。私有 Fork 报告问题时，应下载并附上相关
artifact，同时先移除账号、Key、Cookie 等敏感信息。

旧的 `OPENAI_*`、`GEMINI_*`、`GLM_*` 变量不会再被工作流读取。
