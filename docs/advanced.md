# 高级配置与排查

## 配置模型

项目只公开一组 LLM 配置：

```dotenv
LLM_PROVIDER=openai
LLM_API_KEY=sk-...
LLM_BASE_URL=https://your-provider.example/v1
LLM_MODEL=your-vision-model
```

`LLM_PROVIDER` 选择线上的请求协议。API Key、Base URL 和模型名都属于所选服务，
不能把不同服务的配置混在一起。

## 协议与请求

### `openai`

- 请求：`POST {base}/chat/completions`
- 图片：OpenAI Chat Completions 的 `image_url` data URI
- 结构化输出：JSON Object，并在提示中附加响应 schema

### `openai-responses`

- 请求：`POST {base}/responses`
- 图片：Responses API 的 `input_image` data URI
- 结构化输出：`text.format` JSON Schema

### `gemini`

- 请求：`POST {base}/models/{model}:generateContent`
- 图片：原生 Gemini `inlineData`
- 结构化输出：`responseMimeType=application/json` 与 `responseJsonSchema`
- API Key：`x-goog-api-key` 请求头

### `claude`

- 请求：`POST {base}/messages`
- 图片：原生 Claude base64 image block
- 结构化输出：`output_config.format` JSON Schema
- API Key：`x-api-key` 请求头

四种协议共享请求重试、HTTP 错误处理、JSON 提取、Pydantic schema 校验和响应缓存。

## Base URL 归一化

程序先将 `LLM_BASE_URL` 归一化为 API 根地址，再拼接具体接口：

1. 移除末尾 `/`。
2. 拒绝非 HTTP(S) 地址、query string 和 fragment。
3. 如果路径中没有版本段：
   - `openai`、`openai-responses`、`claude` 补 `/v1`
   - `gemini` 补 `/v1beta`
4. 已有版本段时保持不变。
5. 根据协议拼接最终接口。

因此 `https://host.example/v1` 会保持原样，`https://host.example` 会变成
`https://host.example/v1`，不会生成 `/v1/v1`。Gemini 使用 `/v1beta`，不要按
OpenAI 的规则手动填 `/v1`。

虽然代码能识别已经包含完整接口的地址，但推荐始终填写 API 根地址。这样切换
`LLM_PROVIDER` 时更容易发现协议不匹配。

## GitHub Actions 变量

推荐：

- Secrets：`EPIC_EMAIL`、`EPIC_PASSWORD`、`LLM_API_KEY`
- Variables：`LLM_PROVIDER`、`LLM_BASE_URL`、`LLM_MODEL`

为兼容现有仓库，工作流也允许将后三项保存为同名 Secrets。Variables 优先。

旧变量不会继续读取：

- `OPENAI_*`
- `GEMINI_*`
- `GLM_*`
- 四个单独的 hCaptcha 模型覆盖变量

所有验证码推理统一使用 `LLM_MODEL`，避免同一次挑战因隐式配置而跨协议或跨模型。

## 常见错误

### `Invalid LLM configuration: LLM_API_KEY is empty`

所选工作流或运行环境没有提供 `LLM_API_KEY`。GitHub Actions 中应将 Key 存为 Secret。

### `Invalid LLM configuration: LLM_MODEL is empty`

没有提供模型名。模型必须支持图片输入，仅支持文本的模型无法解验证码。

### HTTP 404

优先检查：

- `LLM_PROVIDER` 是否与服务实现的协议一致
- `LLM_BASE_URL` 是否误填成控制台地址而不是 API 地址
- 服务是否要求额外的固定路径前缀
- 是否把完整 endpoint 错配给了另一种协议

### HTTP 401 / 403

检查 API Key 是否属于当前服务、是否有模型权限，以及自定义服务是否兼容该协议的
认证请求头。

### 返回内容无法通过 schema 校验

服务可能忽略结构化输出设置，或者模型不擅长图像与 JSON。程序不会吞掉此错误；请查看
日志与 hCaptcha 响应缓存，确认原始返回。

## 实现边界

`app/llm/provider.py` 负责协议序列化与响应解析，`app/llm/urls.py` 负责 URL，
`app/llm/agent.py` 是与 `hcaptcha-challenger` 私有 reasoner 的唯一注入点。若依赖升级
导致注入失效，优先只修复该文件，避免再次引入全局 monkey patch。
