# INTERVAL · 区间

Android 下落式音乐游戏与 Windows 制谱器，当前统一版本 **0.12.0**。仅 Tap / Hold，固定下方判定线，支持横屏 16:9 与 4:3。触点可以位于任意高度，但必须落在谱面指定的二维区域内，并满足音符横向位置与时间判定。

## 下载

- [Android 游戏](https://github.com/ly10yue/MusounD_alpha/releases/tag/v0.12.0)：`Interval-0.12.0.apk`，Android 8.0 / API 26 起。
- [Windows 制谱器](https://github.com/ly10yue/mus_composer_alpha/releases/tag/v0.12.0)：解压 `IntervalComposer-0.12.0-Windows.zip`，运行其中 `IntervalComposer.exe`，保留整个文件夹。
- 本地构建产物在 `dist/Interval-0.12.0.apk` 和 `dist/editor-0.12.0/IntervalComposer/`。

0.12.0 统一区域与线的编辑入口；Ctrl 框选靠近边缘时自动滚动；重叠区域仅显示并集外轮廓；所有公开空间坐标改为 **0–100**。新版文件为 **v6**，自动兼容 Composer 0.11.0 旧坐标。角度、透明度、流速及时间单位不变。详见 [版本与兼容说明](docs/versioning.md)。

## 游玩与制谱

游戏启动后进入选歌页，可选内置示例或导入 `.interval` 歌曲包。设置可调整下落时间 **0.6–4.0 秒**、延迟补偿及打击音效。支持自动演示、暂停续接、结算与本地成绩。

音符绑定可编辑的轨迹线；轨迹位置、透明度、音符流速支持独立时间条与缓动。线和 Hold 的弯折形状竖直下落；Tap 横向位置在下落时固定。持续按住 Hold 时跟随它与下方判定线的交点。区域独立平移、旋转、伸缩，可组合成上下、左右或错位的多个主判定区。

制谱器支持导入歌曲、BPM / 偏移、每拍或每小节细分、Tap / Hold、试听与波形、批量复制删除、撤销重做、工程自动恢复。非 Ogg 音频先转为 Ogg，再开始制谱；试听音乐与打击音共用采样对齐的 PCM 音轨。独立调整打击音量及预览流速。

工具栏分别打开「轨迹 / 四栏编辑」与「区域 / 四栏编辑」。拖出时间长条后填写起止值与变化类型。新线默认位置 50、透明度 0、流速 1；新区域默认全屏、旋转 0°。Ctrl 拖选、Ctrl+C / V 复制粘贴，最早起点对齐当前判定线。

内联 Agent 可通过自然语言编辑线、音符和区域，生成草稿后预览并应用，一步撤销。API 设置提供 Base URL、模型 ID、Key 输入；本机 Qoder Bridge 可使用 `Start-Qoder-Agent.cmd`。仅保存密钥文件引用，不把 Key 写入源码、工程或发行包。

- [制谱器操作说明](editor/README.md)
- [Agent 工具、参数与接入](editor/AGENT.md)
- [文件版本与单位](docs/versioning.md)
- [历史格式结构参考](docs/chart-format.md)
- [AT Flow 示例说明](docs/at-flow.md)

内置 Desultory Signals 示例包含传统 4K 与无轨、轨迹变化、多个移动判定区的组合。0.12.0 更新文件单位与版本，不改变既有音符时间与编排。

## 开发与构建

Android 源码与构建脚本见 [游戏仓库](https://github.com/ly10yue/MusounD_alpha)。本仓库 app/src/main/assets/ 为制谱器共享的示例与音效。

Windows 制谱器：Python 与依赖，根目录运行：

```powershell
python -m pip install -r editor/requirements.txt
python -m pip install pyinstaller
python editor/main.py
python -m unittest discover -s editor/tests -p 'test_*.py'
python editor/tests/smoke_012.py
powershell -ExecutionPolicy Bypass -File editor/build.ps1 -DistPath dist/editor-0.12.0
```

源码分别维护在 [游戏仓库](https://github.com/ly10yue/MusounD_alpha) 与 [制谱器仓库](https://github.com/ly10yue/mus_composer_alpha)。发行文件放在 Releases，Git 不提交构建目录、Key、签名私钥或本机配置。版本元数据见 `release.json`。

第三方依赖与许可见 [制谱器组件说明](editor/THIRD_PARTY.md)。示例歌曲版权归原作者 technoplanet 所有；不包含对该音频的另行授权。
