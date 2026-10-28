# 0.4.0 区域运动验证

日期：2026-10-23。Windows 11 / Python 3.14 / PySide6 6.11.0；Android 10 / API 29 模拟器。

## 通过的检查

- Python 模型共 21 项测试：原格式兼容、区域覆盖、坐标验证，以及新增关键帧边界、匀速/平滑/保持、多圈旋转、两个屏幕比例的矩形几何、移出屏幕、区域裁切后保留动画时间、BPM 重定时、v2 工程和谱面往返。
- 原有 Qt 编辑回归通过，保持固定下方判定线和音符下落。
- 新增 Qt 动画界面回归通过：关键帧增加/修改/删除，取消不修改草稿，实时预览，应用、撤销/重做、自动恢复、保存和导出再导入、16:9 与 4:3 预览、真实 OGG 播放。
- Java 引擎：28 项原有判定检查、20 项移动/旋转区域检查通过；包括旋转后原轴对齐边界不再有效、静止手指被移动区域移出后断 Hold、自动演示跟随区域和屏幕外区域禁止点击。
- 静态原曲 622 音符在 30 / 60 / 120 FPS 下模拟均为满分。
- Android v2 联调：16:9 下 577 项、4:3 下 579 项检查通过。逐项对照 Python 导出的多边形角点与垂直列交点，验证解析、错误缓动/版本拒绝、真实播放、暂停冻结与 Hold 恢复。4:3 运行额外覆盖整首动画示例在两种比例下的 622 Perfect 模拟。
- 新版 Android 静态原曲运行回归 13 项通过；独立 Windows EXE 启动和真实音频播放验证通过（`build/composer-motion.json`，`ok=true`、`frozen=true`、退出码 0）。
- 新 APK 编译和签名验证通过。测试限于模拟器，未进行物理手机检查。

## 重现

```powershell
python -m unittest discover -s editor/tests -p 'test_*.py' -v
python editor/tests/smoke_ui.py
python editor/tests/smoke_motion_ui.py
python tools/make_motion_demo.py
Copy-Item dist/Desultory-Signals-Motion.interval build/editor-tests/motion-demo.interval -Force
powershell -ExecutionPolicy Bypass -File test.ps1
powershell -ExecutionPolicy Bypass -File build.ps1
powershell -ExecutionPolicy Bypass -File tools/build_android_tests.ps1
# 安装 build/Interval-debug.apk 和 build/Interval-tests.apk 后：
adb shell am instrument -w -e aspect 16x9 studio.interval.tests/.MotionSmoke
adb shell wm size 1280x960
adb shell am instrument -w -e aspect 4x3 studio.interval.tests/.MotionSmoke
adb shell wm size reset
```

关键帧与两端预览截图位于 `docs/screenshots/motion/`。UI 测试生成 `build/editor-tests/motion.interval` 和用于跨语言对照的 `motion-parity.json`。可直接试玩的完整示例为 `dist/Desultory-Signals-Motion.interval`。
