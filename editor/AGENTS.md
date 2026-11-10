# 制谱器 Agent 交接说明

核对日期：2026-11-02。适用范围：本目录中的 Windows 制谱器源码，以及为本次制谱器任务服务的构建脚本、文档和测试。本文面向接手开发的编码 Agent；`AGENT.md` 和 `skills/interval-chart-agent/` 描述的是软件内置的制谱 Agent，二者不要混淆。

## 开始工作

1. 先阅读用户当前需求、本文、`README.md` 和 `../release.json`；改文件格式时再读 `../docs/versioning.md`，改检查规则时读 `../docs/chart-check-fix.md`。
2. 执行 `git status --short`，检查已有改动，保留用户和其他任务的内容。不要使用 reset、clean 或整目录覆盖来获得干净工作区。
3. 下列命令均在包含 `editor/` 的工程根目录执行。本机路径为 `C:\Users\Lenovo\Desktop\music game`；移交到其他电脑后使用其实际检出路径。
4. 先定位相关模型和测试，再进行实现。完成用户已授权的工作；不要把常规实现选择额外变成确认流程。

## 当前版本与项目边界

| 项目 | 当前状态 |
| --- | --- |
| 制谱器 | Python / PySide6，0.12.0，包含检查规则修正版 |
| 游戏客户端 | 已迁移至 Godot 4.7.1 / GDScript，0.13.0，见 `../godot/AGENTS.md` |
| 文件格式 | v6；`coordinateScale=100`；`minReaderVersion=0.12.0` |
| 兼容基线 | Composer 0.11.0；已有更早读取分支保留 |
| 对应仓库 | <https://github.com/ly10yue/mus_composer_alpha> |

制谱器仍是 Qt 桌面软件，本次客户端迁移没有把制谱器迁入 Godot。不要无任务依据替换为网页编辑器、Unity 或 Godot 编辑器插件。网页端不属于当前维护范围。客户端和制谱器程序版本已经分开，不要为了与 0.13.0 对齐而擅自修改制谱器或谱面版本。

部分旧 README 段落仍称“同列重叠阻止导出”“多押警告”，`model.py` 顶部也保留早期 v3 描述；这些已经过时。以当前实现、回归测试和 `docs/chart-check-fix.md` 为准。

## 源码地图

| 文件 | 职责 |
| --- | --- |
| `main.py`、`launcher.py` | 主窗口、编辑流程、保存恢复、打包启动与诊断 |
| `model.py` | `Document` / `Note` / `Region`、校验、历史、工程与谱面包读写 |
| `versioning.py` | 程序/格式版本、输入输出坐标转换、旧格式读取 |
| `views.py` | 主音符时间轴与游戏预览 |
| `tracks.py`、`curves.py` | 轨迹、缓动、位置/透明度/独立流速计算 |
| `track_editor.py`、`track_view.py` | 轨迹四栏编辑，`track_dialog.py` 为旧式入口 |
| `region_events.py`、`region_editor.py` | 区域四栏事件与对话框 |
| `motion.py`、`motion_dialog.py` | 区域几何、旋转、可触及性与旧式运动工具 |
| `timeline_edit.py`、`edge_pan.py` | 框选、复制粘贴、批量操作、边缘自动滚动 |
| `numeric.py`、`ui_assets/` | 数字控件、同步策略与上下箭头资源 |
| `audio.py`、`audio_import.py` | 后台解码、波形、非 Ogg 导入转换与持久缓存 |
| `playback_clock.py`、`pcm_preview.py`、`hit_audio.py` | 连续试听时钟、歌曲/打击音/节拍器同采样轨混音 |
| `agent_panel.py`、`agent_client.py` | Agent 面板、请求与异步生命周期 |
| `agent_config.py`、`agent_tools.py`、`agent_units.py` | 配置、受限工具、事务草稿与单位边界 |
| `AGENT.md`、`skills/interval-chart-agent/` | 内置 Agent 的协议说明、提示词、工具 Schema 与示例 |
| `tests/` | Python 单元测试及真实 Qt 控件/音频冒烟检查 |
| `build.ps1`、`windows-version.txt` | PyInstaller 打包与 EXE 版本资源 |

示例歌曲、谱面与打击音来自 `../app/src/main/assets/`。`dist/`、`build/` 是产物，不是修改源码的位置。

## 必须保持的行为

- 仅 Tap / Hold。工程音符为 `Note(id, beat, line, length)`；`length=0` 为 Tap，正值为 Hold。现代音符绑定轨迹，不各自存放独立横坐标；保留旧格式的导入转换。
- 工程时间单位为拍，导出 JSON 为秒。`time=beat*60/BPM`；实际音频时刻为 `time+offset`。不要把 offset 同时写入音符 time 又在播放时再次相加。小节编号从 1 开始、拍数从 0 开始，当前是单一恒定 BPM。
- 判定线固定在视口下方，未来的小节线、Tap 和 Hold 向下落。同一绝对拍对应的横坐标固定；轨迹和 Hold 可以弯折，但形状整体竖直下落。不要恢复成 Tap 沿折线横移的旧方案。
- 轨迹四栏：绑定音符、横向位置、透明度、线上音符流速。新线默认无音符、位置 50、透明度 0、流速 1。位置/透明度/流速时间条彼此独立，视觉流速不改变音乐和判定时间。
- 区域四栏：中心 X/Y、旋转、横向总长、纵向总宽。新区域全屏、中心 (50,50)、旋转 0°、尺寸 100×100。时间条支持起止值与缓动；同时开放的矩形按并集显示和判定，隐藏内部交叠边缘。
- 公共界面、文件、剪贴板及 Agent 的空间数值为百分制；内部几何为归一化单位。X 向右、Y 向下、角度顺时针。透明度 0–1、流速倍率、角度、时间和 BPM 不乘 100。
- Ctrl 拖动框选音符或时间条；靠近上下边缘或移出后自动逐格滚动。粘贴保持相对间隔，最早起点落在当前判定线上。普通滚轮每刻度移动当前细分的一格，向上前进；Ctrl+滚轮用于缩放。
- 数字输入焦点存在时，不得让定时刷新覆盖用户尚未提交的文本，或让全局快捷键吞掉输入框的方向键、复制粘贴和数字操作；保留可点击的上下箭头。
- 导入 MP3、WAV 等非 Ogg 时，先在后台转换为持久缓存的 Ogg，再进行波形、试听与导出；保留原音乐，不向原文件混入音效。打击音和歌曲采用同一 PCM 采样轨混音，不用串行/阻塞播放造成双押错位。
- 所有主要编辑支持撤销/重做；线/区域对话框是草稿，确定整体应用并可一步撤销，取消不污染主工程；保存和自动恢复不得覆盖用户原始歌曲。

### 检查与导出策略

- 不对多押或“超过两根手指”发出警告。
- 音符同列重叠仅为警告：保留音符、允许导出；警告不弹出阻止导出的确认对话框。
- 缺失音乐、无效引用、非法事件、区域段落不连续等真正错误仍阻止导出。同一参数栏的时间条重叠仍是结构错误，不能一并降级。
- 音符相关检查使用音频时间点 `分:秒.毫秒（第 N 拍）` 定位并包含 offset，不显示内部音符序号。
- `.ivproj` 保存编辑工程与歌曲路径，不内嵌音乐；`.interval` 是 ZIP，根目录包含 `chart.json` 和被引用的音乐。不能直接把 PhiEdit / Phigros 私有原谱当作本格式读取。

## 文件格式与跨端修改

v6 根节点的 `version`、`appVersion`、`minReaderVersion`、`coordinateScale` 含义不同。`versioning.py` 在 I/O 边界转换空间单位；读取旧文件时不能按数值大小猜测单位，不能在反复保存时再次乘 100。未知版本和不支持的最低读取版本应明确拒绝，不静默丢弃内容。

改变导出结构、缓动或几何语义时，一并检查 Godot 的 `core/chart_loader.gd`、`core/rhythm_core.gd` 和客户端测试；更新双方版本和兼容文档时以实际变化为依据。旧 Java `app/` 只作为回归参考，当前游戏运行端以 Godot 为准。

## 本机运行与打包

本机已使用 Python 3.14.0。依赖版本见 `requirements.txt`，当前为 PySide6 6.11.0、NumPy 2.4.2、SoundFile 0.13.1；另需 PyInstaller 才能打包。

```powershell
Set-Location 'C:\Users\Lenovo\Desktop\music game'
python -m pip install -r editor/requirements.txt
python editor/main.py
```

需要发布产物时再执行：

```powershell
python -m pip install pyinstaller
powershell -ExecutionPolicy Bypass -File editor/build.ps1 -DistPath dist/editor-0.12.0-checkfix
```

产物为 `dist/editor-0.12.0-checkfix/IntervalComposer/IntervalComposer.exe`。保留整个目录和 `_internal/`，不能单独分发 EXE。打包脚本会收集示例资源、`agent-defaults.json`、skill、UI 图标、许可与文档；缺文件时修正源码/构建依赖，不手工拼接未知版本 DLL。脚本已有 Windows ICU 冲突处理，保留其目的。

启动错误日志：`%LOCALAPPDATA%/IntervalComposer/startup-error.log`。应用配置/缓存使用 Qt `AppLocalDataLocation`；测试应使用自己的应用名称或隔离目录，不清空用户曲库、自动恢复文件和 API 配置。

## 验证方法

纯文档修改只核对引用和命令；代码修改运行相关测试，涉及核心模型/格式时运行整个单元测试集：

```powershell
python -m unittest discover -s editor/tests -p 'test_*.py' -v
```

按改动选真实 UI/音频检查，不必无差别执行所有慢测试：

| 改动 | 检查入口 |
| --- | --- |
| 数字输入、箭头、焦点快捷键 | `python editor/tests/smoke_numeric_ui.py` |
| 基本编辑、导入导出、固定判定线 | `python editor/tests/smoke_ui.py` |
| 轨迹或区域四栏 | `python editor/tests/smoke_tracks_ui.py`、`python editor/tests/smoke_batch_regions.py` |
| 0–100 单位、区域默认值、Ctrl 边缘滚动、并集边缘 | `python editor/tests/smoke_012.py` |
| 试听时钟 / 音频转换 / 多押声音 | `python editor/tests/smoke_playback_timing.py`、`python editor/tests/smoke_audio_import.py`、`python editor/tests/smoke_pcm_sources.py` |
| 内联 Agent | `python editor/tests/smoke_agent_ui.py`，先用无 Key 示例或本地模拟响应 |

部分冒烟脚本会生成 `build/` 报告或 `docs/screenshots/` 图像，运行后核对 Git 差异，别误提交无关输出。发布 EXE 后还可运行打包诊断，等待进程退出并读取 JSON，而非仅确认文件存在：

```powershell
$exe = (Resolve-Path 'dist/editor-0.12.0-checkfix/IntervalComposer/IntervalComposer.exe').Path
$report = Join-Path (Get-Location) 'build/composer-handoff-check.json'
Start-Process -FilePath $exe -ArgumentList @('--verify-output', ('"{0}"' -f $report)) -Wait -PassThru
Get-Content -LiteralPath $report
```

改谱面导出时至少导出再导入一次，并在 Godot 加载该包；有音符、轨迹、区域动画改动时检查 16:9 与 4:3。已有检查规则回归见 `tests/test_validation_policy.py`，兼容旧工程样本见 `tests/fixtures/composer-0.11.0.ivproj`。

## 内联 Agent 接手规则

改工具时同步 `agent_tools.py`、`agent_units.py`、`AGENT.md`、skill 与 Schema；Schema 生成入口为 `../tools/export_agent_schema.py`。工具只操作隔离 `EditSession` 草稿，主工程变化后通过 fingerprint 拒绝旧草稿覆盖；用户应用后整体成为一步撤销。保留取消、超时、参数本地验证和请求轮数限制。

普通测试不调用真实模型、不消耗额度。真实 API/Bridge 联调仅在当前用户任务要求时执行。密钥通过输入框、`INTERVAL_AGENT_API_KEY` 或本机密钥文件引用传入；不写入代码、谱面、skill、测试日志或发行包，不打印现有凭据。Qoder Bridge 的接口、模型与密钥有效性是本机状态，按当前配置检测，不把旧端口或模型名当作保证可用的常量。

## 交付与下一位 Agent

- 根据当前任务范围更新相关文档、测试和版本资源；普通修复不自动提升文件格式。
- Git 新分支使用 `codex/` 前缀；提交只包含本次相关文件。独立制谱器仓库是 `mus_composer_alpha`；`.release-repos/composer` 是本机发布工作副本，不是默认开发目录。
- 不提交 `dist/`、`build/`、缓存、签名、密钥及本机配置。按已有授权发布时保留旧版本与 tag，先核对仓库、产物和哈希，不因本文自动发布。
- 最终交接写明：改了什么、运行了哪些检查及结果、源代码位置、实际产物路径、未验证事项。历史通过记录不能冒充本轮测试；不要把模拟器验证说成真机验证。
