# 内联 Agent 验证记录

日期：2026-10-24。Windows 制谱器版本 0.6.0；Android 仍为 0.5.0，谱面格式仍为 v3。

## 已完成验证

- `python -m unittest discover -s editor/tests -p 'test_*.py'`：38 项通过。覆盖区域运动、范围与相邻矩形保留、非法参数回滚、轨迹和音符工具、工具 schema 同步及 API 地址校验。
- `editor/tests/smoke_agent_ui.py`：真实 Qt 界面与本机 HTTP 模拟 API 联调通过。覆盖查询→错误调用修正→区域动画→校验→最终回复、连续修改草稿、失败后保留先前草稿、预览/应用/撤销/导出、主工程变化后的冲突保护、取消、轮数上限和纯文本澄清。
- 同一联调检查 API Key 密码框、请求认证、配置与工程不保存 Key、请求不包含本地歌曲路径、HTTP 错误不回显凭据。
- 原有 `smoke_ui.py`、`smoke_motion_ui.py`、`smoke_tracks_ui.py` 回归通过。
- Skill 的 `quick_validate.py` 校验通过；执行时使用 Python UTF-8 模式。
- 16:9、4:3 预览及 1024×640 窗口已截图检查。Agent 内容可滚动，草稿操作按钮固定在面板底部。
- PyInstaller 打包成功，最终 EXE 的 `--verify-agent-output` 验证通过：`ok=true`、`agent=true`、622 音符、4 条轨迹、格式 3、音频载入成功、波形解码成功、`frozen=true`。

## 验证边界

后续实测：同日已完成 Qoder Bridge Flash 真实模型联调，结果见 [qoder-agent.md](qoder-agent.md)。以下段落保留最初离线验收的范围。

未使用真实 API Key，未调用付费模型。测试中的模型响应由本机模拟服务提供，验证了网络协议、工具执行及界面工作流；真实模型的自然语言理解质量与第三方 API 兼容性尚待实际接入验证。“无 Key 示例”是固定指令演示，不是本地语言模型。

缩小判定区域可能使原有音符无法触及，检查结果会显示这些问题；Agent 不会因此自动修改用户未要求调整的音符。

接入参数与工具格式见 [Agent 文档](../editor/AGENT.md)。界面截图位于 [screenshots/agent](screenshots/agent)。
