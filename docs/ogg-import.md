# 制谱器 0.10.2 · 导入前统一为 Ogg

导入 MP3、WAV、FLAC、M4A、AAC 等非 Ogg 音频时，制谱器先在后台将其转换为 **48kHz、双声道 Ogg Vorbis**，完成后才生成波形和同步试听。打开旧工程或谱面包中关联的非 Ogg 歌曲也走相同流程。已有 Ogg 歌曲直接使用。

转换过程不修改、覆盖或删除原始歌曲。转换文件保存在本机应用数据目录的 `converted-audio/` 下，按源文件内容和转换参数复用；不与可清理的 `pcm-preview/` 试听缓存混用。工程保存转换后的 Ogg 路径，转换文件不会按“最近六首试听”规则删除。要跨设备传输，请导出包含歌曲的 `.interval` 包。

歌曲转换后，波形、歌曲时长、试听和导出均基于同一份 Ogg。用户在准备期间点击播放，会在完成后从当前游标开始；切换歌曲时过期结果不会挂到新工程。转换失败时停止准备并显示错误，可重新导入歌曲。

转换中暂缓保存 / 导出，避免保存出仍然引用未处理 MP3 的成品；完成后可正常保存。Android 谱面包内为 `music.ogg`。单独导出 JSON 时，会将转换后的 Ogg 一并复制到 JSON 旁边，且不会覆盖同名的不同歌曲。原有 Ogg 的 JSON 导出仍需要保持其歌曲与 JSON 同目录。

转换使用已打包的 Qt 音频解码及 SoundFile / libsndfile Vorbis 编码，无需另装 FFmpeg 或 Python。格式是否能解码取决于本地音频后端对相应编码的支持。

验证使用生成的 6 秒节拍测试音频：

- 固定码率 MP3：44.1kHz 单声道；可变码率 MP3：48kHz 双声道。
- WAV：44.1kHz 单声道 PCM、48kHz 双声道浮点。
- FLAC：22.05kHz 单声道。
- 所有文件转换为实际 Ogg Vorbis，时长与源测试音频相差不足 1ms；每 0.5 秒的节拍点保持在原位置。
- 120 BPM、4 拍一小节的真实播放器推进约 2 秒，已覆盖转换完成前点击播放、保存重开、缓存复用、JSON / 谱面包导出及损坏文件处理。

测量数据见 `docs/ogg-import-tests.json`，测试代码为 `editor/tests/smoke_audio_import.py`。既有 Ogg 播放、四栏编辑、输入、音效、暂停 / 跳转 / 循环和 Agent 继续回归。

发布检查：62 个 Python 单元测试通过；原有 9 组 Qt 编辑器回归及新增导入测试通过。打包后的 Windows EXE 分别完成固定码率 MP3、可变码率 MP3、WAV 的转换与实际播放，四栏界面、原 Ogg 示例试听、Qoder 默认配置检查也通过。

运行 `dist/editor-0.10.2/IntervalComposer/IntervalComposer.exe`，也可使用根目录 `Start-Qoder-Agent.cmd`。Android 沿用 0.9.0。
