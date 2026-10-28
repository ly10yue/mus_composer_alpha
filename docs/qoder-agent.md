# Qoder Bridge 接入与实测

## 启动

双击工程根目录的 `Start-Qoder-Agent.cmd`。它检查本机 Bridge、配置制谱器，然后启动 `dist/editor-0.9.0/IntervalComposer/IntervalComposer.exe`。0.7.0 随程序附带本机默认连接；即使本机配置不存在或模型为空，直接双击新版 EXE 也会自动填好模型和密钥。

启动后的制谱器打开 Agent 页签即可发送指令。先在“判定区域”选中目标矩形；模型生成草稿后预览并应用。为避免混淆，请使用脚本新启动的窗口，之前已经打开的窗口不会获得密钥。

| 参数 | 当前配置 |
| --- | --- |
| Base URL | `http://127.0.0.1:8646/v1` |
| 模型 | `qoder-deepseek-flash`（已实测） |
| 可选模型 | `qoder-deepseek-pro`（接口目录中可用，本次未调用） |
| 请求超时 | 120 秒 |
| 轮数上限 | 8 |
| strict schema | 开启，已通过实测 |
| 密钥来源 | `Qoder-Bridge-main/.runtime/bridge-key`，仅供本机 Bridge 认证 |

脚本默认寻找当前用户桌面的 `Qoder-Bridge-main` 文件夹。它更新制谱器本机 `agent-config.json` 的地址、模型和限额；密钥只通过新进程的 `INTERVAL_AGENT_API_KEY` 环境变量传入，不写入配置、谱面、脚本或日志。同时保存本机密钥文件路径及对应接口的绑定关系。之后直接打开新版 EXE，API Key 密码框也会自动填入；更换 API 地址时自动填入的 Bridge 密钥会清除。

可选命令：

```powershell
# 仅检查服务与模型，不调用推理、不启动制谱器、不修改配置
.\editor\start-qoder.ps1 -CheckOnly

# 选择 Pro；仅启动不会发起模型推理
.\editor\start-qoder.ps1 -Model qoder-deepseek-pro

# Bridge 被移动或端口变化时
.\editor\start-qoder.ps1 -BridgeDirectory 'D:\Qoder-Bridge' -Port 8646
```

脚本不会重启或修改 Bridge，也不会改变其已有客户端配置。模型请求使用 Bridge 已登录的 Qoder 账户，按其正常额度计费。

## 2026-10-24 真实模型测试

使用原生 Qt Agent 面板、真实运行中的 Qoder Bridge 和 Flash 模型，发送原指令：

> 这个判定区从第二小节到第四，在屏幕左半区由下方移至上方

结果通过，约 12.58 秒，共 4 轮 API 请求、3 次工具调用：`get_region` → `animate_region` → `validate_chart` → 最终说明。

- 小节被正确换算为 `[4,12)` 拍。
- 原全屏矩形调整为宽 0.5、高 0.5；起点 `[0,0.5,0.5,1]`，终点 `[0,0,0.5,0.5]`，匀速且无旋转。
- 第 8 拍实际几何为 `[0,0.25,0.5,0.75]`；运动范围外原区域保留。
- 草稿生成期间主工程未改变；应用、整体撤销及 Android 谱面包导出通过。
- 校验 0 错误、1 提示：此专用区域示例没有音符。它用于检查动画，不是完整可玩谱面。

结果工程及导出包位于 `dist/qoder-agent-test/`，截图和原始结果位于 `docs/screenshots/agent/qoder-live.png`、`docs/qoder-agent-result.json`。这证明该指令和本次工具循环实测成功，不代表任意指令或 Pro 模型都已验证。

可重复运行的真实模型测试（会使用账户额度）：

```powershell
python -X utf8 tools/test_qoder_agent.py --run
```

不传 `--run` 时不会发出请求。测试使用独立的新工程和设置目录，不修改用户已有谱面。

## 默认连接修复（0.6.2）

默认连接现随程序以 `agent-defaults.json` 提供，设置打开时重新读取。UTF-8 BOM 配置可正常载入；本机空模型字段自动补齐，其他远程服务配置保留。密钥引用字段仅供宿主读取，不再作为 API 客户端参数传入。

默认配置端到端复测：未给面板注入 Key、未手工配置模型，Flash 4 轮 / 3 次工具调用完成原指令，约 12.35 秒，应用、撤销、导出通过。41 项单元测试与模拟服务界面回归通过。打包程序支持 `--verify-agent-settings-output <report.json>` 检查实际设置对话框，仅记录模型与密钥是否已填入，不输出密钥。
