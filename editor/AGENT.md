# 内联制谱 Agent · 接入与工具说明

运行 `dist/editor-0.12.0/IntervalComposer/IntervalComposer.exe`，右侧选择 **Agent** 页签。无需另装 Python 或 SDK。所有导出统一为 v6，需要 Android 0.12.0；支持 0.11.0 旧谱面坐标迁移。

## 使用

本机 Qoder Bridge 用户可直接运行工程根目录的 `Start-Qoder-Agent.cmd`，无需复制密钥。Flash 已通过真实模型区域运动测试；配置和结果见 [Qoder 接入与实测](../docs/qoder-agent.md)。

1. 在「区域 / 四栏编辑」选择目标区域并确定。旧式分段工具存在未应用草稿时先应用。
2. 进入 **Agent → API 设置**，填写 Base URL、模型 ID 和 API Key。
3. 输入自然语言，例如：**这个判定区从第二小节到第四，在屏幕左半区由下方移至上方**。
4. 点击 **发送 / 生成草稿**。Agent 读取选择、调用受限工具；日志显示工具参数、结果和检查提示。
5. 上方画布显示未应用草稿，可使用原有拍输入框、播放按钮、16:9 / 4:3 比例进行预览。左侧时间轴仍显示主工程，直到应用。
6. 点击 **应用草稿**，主工程一次性更新，`Ctrl+Z` 可整体撤销。继续使用保存工程 / 导出 Android 谱面包按钮。

尚未填写 Key 时，可以点 **无 Key 示例**：它通过同一编辑工具生成固定的“左半区自下向上移动”草稿，用于验证功能；它不是本地大模型，也不会理解任意输入。建议用新建工程演练，选中覆盖第 4–12 拍的段落。

未应用草稿可以继续对话修改。主工程若在生成过程中或生成后发生手工变化，应用会拒绝覆盖，需丢弃草稿并重新发送。停止请求立即取消网络等待并丢弃本次新增编辑；之前已有的待应用草稿保留。关闭软件不会保存 Agent 对话、Key 或未应用的 Agent 草稿。

## API 参数

| 字段 | 必需 / 默认 | 说明 |
| --- | --- | --- |
| Base URL | 默认 `https://api.openai.com/v1` | OpenAI 兼容 API 根路径。自动追加 `/chat/completions`；也接受以此结尾的完整地址。不要填写网页聊天地址。远程使用 HTTPS，本机 localhost/127.0.0.1/::1 可用 HTTP |
| 模型 ID | 必填，无默认模型 | 填服务商账户实际可用、支持 `tools` / function calling 的模型 ID |
| API Key | 远程服务必填 | 密码输入框，已配置的本机 Bridge 密钥自动填入；也可读取 `INTERVAL_AGENT_API_KEY`。不会保存到 JSON、工程、谱面包或源码 |
| 超时 | 默认 45 秒，5–120 | 每次 HTTP 请求限时，超时后丢弃本次运行新增编辑，不自动重试 |
| 最多轮数 | 默认 8，1–12 | 模型请求轮数，包含读取、编辑与最终回复；每任务额外限制 ≤32 次工具调用、每轮 ≤8 次 |
| 严格 schema | 默认开启 | 发送 function 的 `strict:true`；若兼容服务不支持，可关闭。宿主本地参数校验始终开启 |

本机配置文件位于 Qt `AppLocalDataLocation/agent-config.json`，可在 Windows 的 `%LOCALAPPDATA%/Interval/IntervalComposer/` 下找到（不同启动方式可能使用不同应用目录）。普通 API 配置示例：

```json
{
  "base_url": "https://api.openai.com/v1",
  "model": "服务商提供的模型ID",
  "timeout": 45,
  "max_rounds": 8,
  "strict": true
}
```

也可以在启动制谱器的 PowerShell 会话中设置 `$env:INTERVAL_AGENT_API_KEY`。不要把 Key 写进 skill、工具参数、谱面或版本控制。本机已授权的 Qoder Bridge 使用 `default_key_file` 指向原密钥文件，`default_key_endpoint` 绑定其本机接口；只保存引用，不复制密钥。更换接口时自动填入的密钥清除。

只有点击发送才会发起 API 请求。发送内容包括用户指令、面板近期对话、必要的谱面元数据、选择信息及工具查询结果；不会上传音频二进制或本地歌曲路径。请求使用 `Authorization: Bearer <key>`，不跟随重定向。调用可能消耗服务商额度。

当前使用 **非流式 Chat Completions**，不支持仅提供 Responses、Anthropic Messages 或网页聊天接口的端点。请求形状：

```json
{
  "model": "模型ID",
  "messages": [{"role": "system", "content": "skill内容"}, {"role": "user", "content": "上下文与指令"}],
  "tools": [{"type": "function", "function": {"name": "工具名", "description": "用途", "strict": true, "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": false}}}],
  "tool_choice": "auto",
  "stream": false
}
```

模型返回 `choices[0].message.tool_calls` 后，宿主按顺序校验/执行，将 `role:"tool"`、`tool_call_id` 和 JSON 结果回传模型。最终回复必须正常结束。截断、无效响应、HTTP 错误或限额耗尽不会自动应用任何编辑。API 结构依据 [OpenAI 官方 Function calling 文档](https://developers.openai.com/api/docs/guides/function-calling) 和 [Chat Completions 参数](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create)。

## 时间与坐标约定

- 内部工具时间为 **绝对拍数**；导出时才换成秒。小节编号从 **1** 开始，拍数从 **0** 开始。
- 第 N 小节开头：`(N−1) × meter`。默认每小节 4 拍，“第二小节开头至第四小节开头”对应 `[4,12)`；若包括第四小节全部内容，则写“到第四小节结束”，对应 `[4,16)`。
- 坐标范围 0–100，X 向右、Y 向下；矩形为 `[left,top,right,bottom]`。左半屏 X 为 0–50；从下到上意味着 Y 递减。
- 区域动画是相对基础矩形中心的平移和旋转；X/Y 位移范围 ±200，角度范围 ±36000，正角度顺时针。可用区域四栏时间条随时间改变中心点、角度、总长和总宽。
- `ease`：`linear` 匀速，`smooth` 平滑，`hold` 保持至下一帧。
- 区间 `[start_beat,end_beat)` 左闭右开，终点属于后一段。范围外原状态保留；需要运动完成后保持在上方时，请明确要求后续保持区间。

## 工具接口

完整可执行 JSON Schema 在 [skills/interval-chart-agent/references/tool-schema.json](skills/interval-chart-agent/references/tool-schema.json)。全部字段必填，禁止额外字段，索引从 0 开始。

| 工具 | 主要参数 | 作用 |
| --- | --- | --- |
| `get_context` | `{}` | BPM、拍号、游标、原始选择、轨迹概要 |
| `list_regions` | `offset, limit` | 区域段分页，limit 1–32 |
| `get_region` | `region_index, rect_index` | 指定矩形及运动帧 |
| `get_track` | `line_id` | 指定轨迹的全部关键帧 |
| `get_notes` | `start_beat, end_beat, offset, limit` | 音符分页，limit 1–200 |
| `animate_region` | `region_index, rect_index, start_beat, end_beat, start_rect, end_rect, start_angle, end_angle, ease` | 在所选段落内部修改一个矩形，保留其他矩形与范围外内容 |
| `set_region` | `start_beat, end_beat, label, rects, motions` | 明确替换一个时间范围内整组矩形；允许跨段 |
| `set_track` | `line_id, name, frames` | 新增轨迹或替换其全部关键帧 |
| `set_track_events` | `line_id, channel, events` | 单独替换 x/alpha/speed 时间条，保留其他通道 |
| `delete_track` | `line_id` | 删除无音符绑定的线，至少保留一条 |
| `set_region_center` | `region_index, rect_index, events` | 中心点时间条，from/to 为 [X,Y] |
| `set_region_events` | `region_index, rect_index, channel, events` | angle/width/height 时间条 |
| `edit_notes` | `notes:[{id,beat,line,length}]` | `id:null` 新建，整数 ID 修改；length 0 为 Tap，正数为 Hold |
| `delete_notes` | `ids:[整数ID]` | 删除明确指定的已有音符 |
| `validate_chart` | `{}` | 返回可玩性检查结果，不擅自修复其他内容 |

例：选中第 0 段第 0 个全屏矩形，段落覆盖 4–12 拍。为满足“左半屏、从下到上”，将它调整为宽 50、高 50：

```json
{
  "name": "animate_region",
  "arguments": {
    "region_index": 0, "rect_index": 0,
    "start_beat": 4, "end_beat": 12,
    "start_rect": [0, 50, 50, 100],
    "end_rect": [0, 0, 50, 50],
    "start_angle": 0, "end_angle": 0,
    "ease": "linear"
  }
}
```

`set_region.motions` 可为 `[]`，否则与 rects 一一对应。每个元素是一组 `{beat,x,y,angle,ease}`。`set_track.frames` 是 `{beat,x,alpha,ease}`，其中 x 为 0–100、alpha 为 0–1。矩形和轨迹每条最多 256 帧，时间严格递增；每段最多 32 个矩形，每谱最多 64 条轨迹、20000 音符。更完整例子见 [examples.md](skills/interval-chart-agent/references/examples.md)。

## Skill 与扩展入口

- Skill：`editor/skills/interval-chart-agent/SKILL.md`。每次请求加载到 system message，约定意图解析、范围保留、坐标及工具使用。
- 工具：`editor/agent_tools.py` 的 `TOOLS` 和 `EditSession._dispatch`。工具没有 shell、任意代码、文件读写、联网或保存/导出能力；真实网络仅由固定 API 客户端处理。
- 网络：`editor/agent_client.py` 的 `AgentClient`。API Key 参数为 `api_key`，没有硬编码凭据；可以替换此层接入其他协议。
- UI：`editor/agent_panel.py`。应用前比对工程指纹与实例，避免覆盖等待期间的手工修改。
- 打包后可编辑 EXE 同目录的 `skills/interval-chart-agent/SKILL.md`，下次发送生效；工具 schema 仍由程序代码控制。外部 skills 目录缺失时使用 `_internal/skills`。

新增工具时修改 allowlist/schema 和 dispatcher，在本地验证约束，再运行 `python tools/export_agent_schema.py` 更新文档；只改 skill 不能新增程序权限。为新增能力添加行为测试，再重新打包。

## 验证范围

已提供真实 Qt 控件 + 本机 HTTP 模拟服务的联调测试，覆盖多轮 tool_calls、错误修正、草稿预览、应用/撤销/导出、API Key 输入不落盘、取消和旧草稿冲突。这些离线测试不调用付费模型，不使用用户凭据。另于 2026-10-24 使用本机 Qoder Bridge 的真实 Flash 模型完成原区域移动指令的端到端验证，见上述 Qoder 文档；其他模型和服务仍需分别验证。

```powershell
python -m unittest discover -s editor/tests -p 'test_*.py'
python editor/tests/smoke_agent_ui.py
python -X utf8 C:/Users/Lenovo/.codex/skills/.system/skill-creator/scripts/quick_validate.py editor/skills/interval-chart-agent
powershell -ExecutionPolicy Bypass -File editor/build.ps1 -DistPath dist/editor-0.12.0
```

0.12.0 空间参数统一为 0–100；透明度 0–1、流速倍数、角度度数、时间拍数不变。工具上下文声明 appVersion 与 coordinateScale。区域中心条例：`from:[25,75], to:[25,25]`；线位置条例：`from:20, to:80`。
