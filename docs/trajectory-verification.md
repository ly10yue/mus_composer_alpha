# 轨迹与弯折音符验证 · 0.5.0

验证日期：2026-10-24。Windows 原生 PySide6 制谱器，Android 29 x86_64 模拟器；1280×720 和 1280×960。尚未在实体 Android 设备上校准音频或触控延迟。

## 实现

- v3 的音符保存轨迹 ID、时间与 Hold 持续时间，不保存横坐标。轨迹包含独立位置、线透明度、过渡关键帧。
- 下方固定判定线不动；轨迹变化逐段向上传递，Tap 沿路径下落，Hold 按多个采样点形成带状折线。采样包含精确关键帧拐点。
- 判定取轨迹下方交点的实时横坐标，触点高度仍由二维判定区域限制。移动 Hold、自动演示、暂停恢复共用这一逻辑。
- 编辑器支持轨迹增删、重命名、关键帧编辑、预览、音符改绑、撤销重做、导出与旧格式迁移。透明度只控制线，音符保持可见。
- 内置曲目与 `Desultory-Signals-Trajectory.interval` 更新为 4 条轨迹、622 音符（588 Tap / 34 Hold）；开场首音符延长为 1.4 秒 Hold 以展示弯折。

## 验证结果

| 检查 | 结果 |
| --- | --- |
| Python 模型、区域、轨迹测试 | 28 项通过 |
| JVM 判定回归 | 28 项通过 |
| JVM 运动矩形回归 | 20 项通过 |
| JVM 轨迹、延迟路径、移动 Hold、暂停续接 | 13 项通过 |
| 完整 622 音符轨迹谱面 | 30 / 60 / 120 FPS 均全 Perfect；Android 同时覆盖两种比例 |
| Qt 基础编辑 UI | 鼠标放置、移动、Hold 尾编辑、细分、导出、播放等通过 |
| Qt 区域 UI | 关键帧编辑、草稿、撤销、预览、导入导出通过 |
| Qt 轨迹 UI | 轨迹/关键帧增删改、禁止删除已绑定轨迹、取消、改绑、折线预览、保存/导出/自动恢复通过 |
| Android TrackSmoke | 16:9 与 4:3 各 545 项通过；包含 Python/Java 路径及透明度对照、非法谱面拒绝、v1/v2 兼容、音频播放和 Hold 暂停续接 |
| Android 区域回归 | 16:9、4:3 各 579 项通过；16:9 另验证新版轨迹与运动区域组合示例 |
| Android 导入与导航 | 12 项导入检查、29 项标题/曲库/导航检查通过 |
| Android 游戏流程回归 | 16:9 的 13 项通过；远离判定线点击、暂停、区域限制、自动演示与结算 |
| 打包 Windows EXE | 隐藏窗口实际启动，载入 622 音符/4 条轨迹/v3 谱面，播放 OGG、解码波形，进程退出 0 |

## 复现

```powershell
python -m unittest discover -s editor/tests -p 'test_*.py'
.\test.ps1
python editor/tests/smoke_ui.py
python editor/tests/smoke_motion_ui.py
python editor/tests/smoke_tracks_ui.py
.\build.ps1
.\tools\build_android_tests.ps1
```

`TrackSmoke` 使用桌面 UI 测试导出的 `build/editor-tests/tracks.interval` 与 `tracks-parity.json`。模拟器启动后安装两个 APK，执行 `adb shell am instrument -w -e aspect 16x9 studio.interval.tests/.TrackSmoke`；将屏幕改为 1280×960 后以 `aspect 4x3` 再运行。

截图位于 `docs/screenshots/trajectories/`：关键帧对话框、两个比例的编辑器与预览、两个比例的 Android 实际画面。已查看，Hold 的头/中段/尾部呈现不同横向位置，判定线保持水平固定。

轨迹 Hold 的可触及性检查采用有限采样，不等同于连续数学证明；急速运动和多个轨迹相交仍需手动试玩确认手感。当前只支持恒定 BPM、横向轨迹位置动画；判定区域继续支持二维移动和旋转。
