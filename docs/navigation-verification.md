# 0.3.0 初始界面与选歌验证

2026-10-22，Android 10 / API 29 模拟器；1280×720（16:9）与 1280×960（4:3）。

## 页面与数据

- 新启动进入初始界面，提供进入选歌、玩法说明与设置入口。
- 曲库后台扫描内置歌曲和应用内部所有导入谱面；元数据与游戏引擎分开保存，进入演奏时才创建播放器。
- 选歌页支持每页四首、按钮翻页与横向滑动，展示歌曲详情和各谱面的最高分。
- 导入成功后留在选歌页并选中新谱面；取消或导入失败不丢失已有曲库。
- 从设置返回原页面；暂停、结算返回当前选曲；重启记住所选谱面，但仍先显示初始界面。
- 沿用原有歌曲存储目录和成绩键，升级无需重新导入旧谱面。

## 自动验证

- `NavigationSmoke`：16:9 与 4:3 各 29 项通过，包括实际按钮点击、多文件曲库、分页、长标题、系统选择器取消、真实谱面包导入回调、演奏与自动演示、暂停和结算返回、播放器释放、重新启动与选曲恢复。
- `Smoke`：16:9 与 4:3 各 13 项游戏运行回归通过，覆盖音频准备、远离判定线的有效触点、暂停恢复、二维区域和完整 622 音符演示。
- `test.ps1`：28 项判定检查通过；整曲在 30 / 60 / 120 FPS 下均为 622 Perfect、1,000,000 分。
- APK 编译与签名校验通过。未进行物理手机测试。

执行方式：

```powershell
powershell -ExecutionPolicy Bypass -File build.ps1
powershell -ExecutionPolicy Bypass -File test.ps1
powershell -ExecutionPolicy Bypass -File tools/build_android_tests.ps1
# 安装 build/Interval-debug.apk 与 build/Interval-tests.apk 后：
adb shell am instrument -w -e aspect 16x9 studio.interval.tests/.NavigationSmoke
adb shell am instrument -w -e aspect 16x9 studio.interval.tests/.Smoke
adb shell wm size 1280x960
adb shell am instrument -w -e aspect 4x3 studio.interval.tests/.NavigationSmoke
adb shell am instrument -w -e aspect 4x3 studio.interval.tests/.Smoke
adb shell wm size reset
```

导航测试使用桌面测试导出的 `build/editor-tests/roundtrip.interval` 创建临时曲库样本，测试结束删除这些样本。测试截图中的 Navigation test、长标题测试曲目仅用于验证分页与文字截断，未打包进游戏。截图位于 `docs/screenshots/menus/`。
