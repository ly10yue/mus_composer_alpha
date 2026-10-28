# 验证记录

日期：2026-10-22。构建：0.1.0 debug。

## 结果

- 原生 APK 构建成功，APK v2 / v3 签名验证通过。
- JVM 判定测试：28 项通过，覆盖时间窗、二维区域、横向对位、双押、Hold 松手与移出、暂停续接、取消和重开。
- 谱面静态检查：622 个音符、8 段连续区域；无区域外不可判音符、同列重叠或超过双指的组合，Hold 不跨区域切换。
- 整曲模拟：30 / 60 / 120 FPS 均为 622 Perfect，0 Miss，1,000,000 分。
- Android 10 / API 29 x86_64 模拟器：1280×720（16:9）与 1024×768（4:3）各 13 项运行测试通过。
- 实际设备内检查包含音频加载、开始按钮、远离判定线的有效点击、暂停时音频与谱面冻结、恢复播放、上下区与双区限制、自动演示及结算。
- 已检查两种比例的界面截图。运行期间无 AndroidRuntime 崩溃记录。

设备内测试会跳转音乐时间以快速覆盖区域段落，所以部分截图中的 Miss 属于测试主动跳过音符的结果。结算截图由同一判定引擎在 Android 进程内完成整谱模拟生成，不代表真人游玩成绩。

## 复现

```powershell
powershell -ExecutionPolicy Bypass -File .\build.ps1
powershell -ExecutionPolicy Bypass -File .\test.ps1
powershell -ExecutionPolicy Bypass -File .\tools\build_android_tests.ps1
$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
& $adb install --no-incremental -r build\Interval-debug.apk
& $adb install --no-incremental -r build\Interval-tests.apk
& $adb shell wm size 1280x720
& $adb shell am instrument -w -e aspect 16x9 studio.interval.tests/studio.interval.tests.Smoke
& $adb shell wm size 1024x768
& $adb shell am instrument -w -e aspect 4x3 studio.interval.tests/studio.interval.tests.Smoke
& $adb shell wm size reset
```

模拟器首次准备可运行 `python tools/setup_emulator.py`，它会下载并验证官方 Android 10 系统镜像，再创建名为 `Interval` 的本地 AVD。测试 APK 独立于应用 APK，不需要交付给玩家。

当前未在物理 Android 手机或平板上测试。触控采样、扬声器/蓝牙输出延迟及特定设备刷新率的实际体验需真机验证；游戏设置提供手动延迟补偿。

截图位于 `docs/screenshots/device/`。
