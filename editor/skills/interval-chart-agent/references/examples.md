# 参数和例子

工具的唯一权威 schema 是 `tool-schema.json`，由 `editor/agent_tools.py` 导出。工具名采用 snake_case；所有对象拒绝额外字段；所有 schema 字段均必填。

## 区域移动

指令：“这个判定区从第二小节到第四，在屏幕左半区由下方移至上方。”

假定每小节 4 拍，选中第 0 段第 0 个矩形，原矩形为全屏且段落覆盖第 4–12 拍：

```json
{
  "name": "animate_region",
  "arguments": {
    "region_index": 0,
    "rect_index": 0,
    "start_beat": 4,
    "end_beat": 12,
    "start_rect": [0, 50, 50, 100],
    "end_rect": [0, 0, 50, 50],
    "start_angle": 0,
    "end_angle": 0,
    "ease": "linear"
  }
}
```

结果：原区间被切为前段、运动段、后段；只有运动段中的目标矩形改变，其他矩形的关键帧不变。运动帧绝对拍数为 4 和 12，位移从 `(0,0)` 到 `(0,-50)`。时间范围左闭右开，12 拍开始恢复后段原状态；想在上方停留需另行设置后续区域段。

如果原矩形宽 20、高 20，可保持尺寸，用 `[0,80,20,100]` → `[0,0,20,20]`，而不是一律改成半屏。

## 轨迹关键帧

```json
{
  "name": "set_track",
  "arguments": {
    "line_id": "line1",
    "name": "左轨迹",
    "frames": [
      {"beat": 0, "x": 18, "alpha": 1, "ease": "linear"},
      {"beat": 4, "x": 18, "alpha": 1, "ease": "smooth"},
      {"beat": 12, "x": 35, "alpha": 0.4, "ease": "linear"}
    ]
  }
}
```

## 音符

```json
{
  "name": "edit_notes",
  "arguments": {
    "notes": [
      {"id": null, "beat": 4, "line": "line1", "length": 0},
      {"id": null, "beat": 8, "line": "line1", "length": 2}
    ]
  }
}
```

`id=null` 由宿主生成新 ID；整数 ID 必须已经存在。音符不保存横坐标。细分拍数可以使用小数（例如 1/6 拍为 0.16666667）；工具不自动吸附当前网格。

## 读取

- `get_context({})`：拍号、时长、当前游标、选择和轨迹概要。
- `list_regions({"offset":0,"limit":16})`：当前段落索引、范围、矩形和运动帧数。
- `get_region({"region_index":0,"rect_index":0})`：一个矩形的完整运动数据。
- `get_track({"line_id":"line1"})`：轨迹全部关键帧。
- `get_notes({"start_beat":0,"end_beat":16,"offset":0,"limit":100})`：指定范围内音符；超过 limit 时分页读取。
- `validate_chart({})`：错误和警告数量，分别返回前 20 条。

## 限制

每段 ≤32 个矩形，每矩形 ≤256 帧，区域总帧数 ≤20000；每谱 1–64 条轨迹，每轨迹 1–256 帧；音符总数 ≤20000；`edit_notes` / `delete_notes` 单次 ≤1000 个。拍数 ≤600000，区域动画位移 ±200、旋转 ±36000 度，透明度为 0–1，轨迹 X 为 0–100。`ease` 为 `linear`、`smooth` 或 `hold`。


## 线流速与区域中心点时间条

第 2 小节到第 4 小节（4 拍一小节）对应 4～12 拍。先 get_track / get_region 读取原有条目；下例假设该栏原来为空，否则要合并未修改部分：

```json
{"name":"set_track_events","arguments":{"line_id":"line1","channel":"speed","events":[{"start":4,"end":12,"from":1,"to":2,"ease":"sine_in_out"}]}}
```

```json
{"name":"set_region_center","arguments":{"region_index":0,"rect_index":0,"events":[{"start":4,"end":12,"from":[25,75],"to":[25,25],"ease":"sine_in_out"}]}}
```

`set_region_events` 参数为 region_index、rect_index、channel、events；channel 为 angle/width/height，时间条 from/to 使用数字。角度为度数，总长宽以游戏区域 0–100 表示。保存为 v6，由 Android 0.12.0 读取。
