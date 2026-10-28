> 此为 r1 历史记录。当前同名谱面已升级 r2；旧谱保存在 dist/AT-Flow/archive/Desultory-Signals-AT-Flow-r1.interval。

# Desultory Signals · AT Flow

2026-10-25。单张完整谱面，传统 4K、运动段与综合段按乐句交替，不是三张独立难度。Android 0.7.0 / 制谱器 0.8.0 已内置。

## 直接打开

- 游戏：安装 `dist/Interval-0.7.0.apk`，选歌页选择 **Desultory Signals / AT Flow**。
- 制谱器：运行 `dist/editor-0.8.0/IntervalComposer/IntervalComposer.exe`，点击 **示例谱面 → AT Flow · 4K / 区域 / 综合演出**。
- 独立文件：`dist/AT-Flow/Desultory-Signals-AT-Flow.interval` 可同时被游戏和制谱器导入；同目录 `.ivproj` 是可编辑工程。

歌曲保持原始 202 BPM。共 **998 个音符：974 Tap、24 Hold**。所有音符头都使用用户提供的 `AT.json` 中的原始踩音，没有另加偏离原谱时间的音符头；位置、键型、部分 Hold 时长及演出重新设计，Drag/Flick 转为 Tap。源文件 SHA-256 与逐项统计保存在 [at-flow-analysis.json](at-flow-analysis.json)。

## 编排

| 时间（约） | 段落 | 编排与变化 |
| --- | --- | --- |
| 0–9.50s | INTRO | 双轨与开场长 Hold，保留原谱前奏留白 |
| 9.50–33.27s | GROOVE | 传统 4K，交互、跨手双押，给出稳定读谱参照 |
| 33.27–42.77s | LIFT | 外侧轨迹退场，主区连续上移，降低密度 |
| 42.77–66.53s | WEAVE | 4K 与小幅轨迹摆动结合，Hold 展示竖直下落的弯折 |
| 66.53–80.79s | AIR | 旋转与留白，主区缓慢升降，附区从屏外进入 |
| 80.79–90.30s | GARDEN | 双轨、附区进退及旋转，主区连续回到下方 |
| 90.30–114.06s | RETURN | 四轨展开，加入横向间距的缓慢变化 |
| 114.06–118.81s | BREATH | 降密度，演出线加入，最多六条可见线 |
| 118.81–142.57s | SIGNALS | 4K、线摆动、线透明度、主区升降旋转和附区结合 |
| 142.57–150.75s | OUTRO | 外侧轨迹退场，回归双轨与平缓收束 |

四条演奏轨与两条无音符演出线共用原有关键帧系统。增减通过透明度渐入/退场表现，可见线数量在 **2–6** 之间变化，不会删除仍被音符绑定的 ID。演奏轨在音符头处的透明度不低于 0.5；完全隐去的线不承担打击。

主区始终是同一个尺寸的矩形，用共用的全曲运动帧进行平移、升降和小幅旋转；所有段落交界处主区多边形的坐标完全一致，边界跳变为 **0**。矩形数量在 **1–4** 之间变化，新增附区先在屏外，再平滑进场，离场后才从段落移除。附区仍属于可判定区域并集，但没有单独音符；每个音符及 Hold 全程都能仅依靠主区完成。

## 难度口径

目标按 **Malody 4K Regular 10dan 以内**保守编写，重点限制同指连打、连续高密度和多押，运动段额外减密度。实际检查结果：

| 指标 | 结果 |
| --- | --- |
| 单秒峰值音符头 | 13 |
| 四秒窗口最高平均 | 12.75 头/秒 |
| 八秒窗口最高平均 | 12 头/秒 |
| 同轨相邻音符头最短间隔 | 176.4ms |
| 最大同押 | 2 |
| Hold 与新音符合计最高同时输入数 | 2 |
| 主区可触及性 | 每个音符和 Hold 均通过 16:9 / 4:3 检查 |

以上是本谱采用的工程约束，不是 Malody 官方的段位换算公式。Malody 官方公告给出了 Regular 的判定与通过口径，制作组说明还包含多人试玩和排列审查流程；因此本谱的段位目标仍应由实际玩家试玩复核，不能仅凭 NPS 视为已认证。参考：[官方 v3 公告](https://www.taptap.cn/moment/243752492733563922)、[制作组的 v3 说明](https://www.bilibili.com/opus/628463670870260863)。

## 打击音效

游戏使用预载入的 SoundPool：Tap 成功和 Hold 头各播放一次，Miss、Hold 尾和暂停续接不重复响。自动演示也使用同样的判定回调。游戏“设置”可开关打击音效。

制谱器通过音频时钟与 5ms 精确计时器调度音符头，使用多声部 QSoundEffect 播放同一组原创短 PCM 音效。底部可开关并调整音效音量，节拍器独立控制。暂停不补响，拖动进度只从新位置开始，循环会重新播放对应区间，静音后重新开启不补播历史音符。

音效由 `tools/make_hit_sounds.py` 合成。Android 使用 `res/raw/hit_tap.wav` / `hit_hold.wav`，制谱器使用 `assets/sfx/` 下相同 PCM；没有新音效下载或运行时联网依赖。

## 验证与复现

- 45 项 Python 单元测试通过。
- Qt 真实音效/播放测试通过：资源载入、和弦多声部、Hold 尾不重复、暂停续播、定位、静音重开、循环。
- AT 谱面编辑器测试通过：八个演出场景、16:9 / 4:3、1024×640 下的音效控件、导出重导入。
- Android FlowSmoke 在 16:9 / 4:3 各 **6924** 项检查通过：新内置曲、桌面包解析、主区单独可触及、边界连续、全曲 30/60/120 FPS 满分演奏、实际 SoundPool 打击/静音/暂停行为。
- Android 曲库导航回归通过，原有基础谱面继续保留。

```powershell
python tools/make_hit_sounds.py
python -X utf8 tools/make_at_showcase.py --reference 'C:\Users\Lenovo\Desktop\DesultorySignals.technoplanet.0\AT.json'
python -m unittest discover -s editor/tests -p 'test_*.py'
python editor/tests/smoke_hits_ui.py
python editor/tests/smoke_at_flow_ui.py
```

截图位于 `docs/screenshots/at-flow/`。完整源代码包为 `dist/Interval-source.zip`。
