# 弯折 Hold 竖直下落 · 验证记录

日期：2026-10-25。Android 游戏 0.6.0，Windows 制谱器 0.7.0，谱面格式 v3。

## 行为

轨迹关键帧描述各绝对时间的横坐标 `X(s)`。当前时间只改变高度：`y = judgementY - (s-now)*speed`。因此轨迹线和 Hold 具有折线形状，同一个折点和同一段下落时横坐标固定，整个形状向下经过固定判定线。Tap 的横坐标固定为它的判定时间对应的 `X(note.time)`。

Hold 沿整个持续区间的轨迹绘成带状多边形，不拉直。按住后的头部在下方判定线裁切，持续输入仍需跟随此交点的横坐标；触摸高度仍由二维判定区域决定。Tap 与尚未按下的 Hold 头在时间容差窗口内按自身起始横坐标判定。

保持过渡使用关键帧前的采样保留横向折角；连续过渡不额外插入几乎重合的顶点，避免 Android 路径填充产生尖三角。旧 v3 工程和谱面直接采用新行为；查看效果需要新版游戏。

## 测试

- Python 单元测试：42 项通过，覆盖线形状、Tap 固定横坐标、Hold 各段横坐标、输入范围、碰撞、谱面往返和 Agent 默认设置。
- JVM：28 项基本判定、20 项区域移动/旋转、49 项轨迹与 Hold 检查通过。相同 Hold 在两个时刻的全部绝对采样点完全一致；时间只改变渲染纵坐标。
- 内置 622 音符谱面在 30/60/120 FPS 下均为 622 Perfect、0 Miss、满分。
- Qt：轨迹/关键帧编辑、Hold 折线顶点仅竖直位移、16:9/4:3 预览、导出重导入、播放与自动恢复通过。原有基础编辑、区域动画和 Agent 面板回归通过。
- Android 模拟器：16:9、4:3 的 TrackSmoke 各 545 项通过，包含 Python/Java 路径和透明度一致、v1/v2 兼容、非法数据拒绝、真实音频播放、Hold 暂停续接以及两种比例/三种帧率的全曲演示。
- Windows EXE：载入 622 音符 / 4 轨迹，播放 OGG、解码波形、Agent 草稿预览通过；默认模型和遮罩 Key 设置检查通过。

截图位于 `docs/screenshots/vertical/`。示例 `dist/Desultory-Signals-Vertical.interval` 保留 622 音符和 4 轨迹，开场长 Hold 展示弯折形状向下经过判定线。

## 产物

- `dist/Interval-0.6.0.apk`
- `dist/editor-0.7.0/IntervalComposer/IntervalComposer.exe`
- `dist/Desultory-Signals-Vertical.interval`
- `dist/Interval-source.zip`

制谱器继续使用已配置的 Qoder Bridge 默认连接。`Start-Qoder-Agent.cmd` 指向 0.7.0。数据格式、工具参数与运动公式见 [chart-format.md](chart-format.md) 和 [制谱器说明](../editor/README.md)。
