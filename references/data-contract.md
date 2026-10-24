# 数据契约与功能模板

## 原生输入

导入需要三份彼此匹配的不可变文件：

1. 完整快照 JSON，接受 `{result: ...}` 或日志里的 `{response:{result:...}}`。
2. 同一版本的原生 SVG，不修改文字或图形来掩盖问题。
3. 本包 `measure` 生成的测量 JSON。

快照 `result` 必须有 `wiresAvailable:true`、`pinNetsAvailable:true`、`components`、`wires`、`pagePrimitives.attributes`。每个实体元件有真实 `primitiveId/designator/uniqueId/device/footprint/symbol`、位置、旋转、mirror、bbox、完整 pins；`pinsAvailable:true`，每个 pin 有 `pinNumber/pinName/x/y/rotation/net/noConnected/netAmbiguous`。未知不能当 NC。

SVG 需包含每个原生元件 `c_partid="part"` 分组，组内 ID 能与 primitiveId/属性 ID 对应。Name 与 Designator 可见属性由真实快照识别，其余可见文字按固定文字处理。该结构与当前 easyeda-agent 导出契约相关，不能保证所有 SVG 格式通用。

模型 `schemaVersion=1` 使用 raw、Y-up；常用网格 5 raw，保留真实半网格坐标。`rotation` 是实测正方向的四分之一转。当前模型不接受 mirror。`parts[].native` 保留输入身份，几何变换仅更新外层位置/引脚/文字包围盒。

多个源页用 `combine` 合并，模型和 SVG ID 加页前缀，`native` 身份不变；每个元件必须有全工程唯一的位号。合并前，检查不同页的同名局部网络是否实际不同，避免迁到同一页后意外连接。

## 实测网名与标题

`extra_texts.json` 是数组。字符串是新增原生网名，对象是另行测量的标题：

```json
["GND", "3V3", "IN1", "LOCAL_SIGNAL", {"text":"Controller", "fontSize":12}]
```

`measure` 输出 `elements`（原图包围盒）、`textMetrics`（7.0062 raw 字形）、`nativeLabelMetrics`（原生标签基线边界）、`annotationMetrics`（标题）。功能模板涉及的全部网名必须可测，不能用字符串长度兜底。

不同工程可能把 GND 文字置于右侧或居中下方。先取得同一工程至少两个零度 GND 的原生快照及 SVG 实测，再运行：

```powershell
python scripts/layout.py calibrate-ground --snapshot ./actual/snapshot.json --measurements ./actual/measurements.json --out ./work/ground-profile.json
```

输出只包含相对符号连接点的 `relativeBBox`、`rotation:0`、样本数与输入文件哈希。多个样本的边界需一致；不修改输入。将该对象放到**新的派生测量文件**的 `nativeGroundLabelProfile` 字段，并让 manifest 的 `measurements` 引用派生文件。原始 SVG 和测量文件保持不变。

提供 profile 后，接地搜索只采用已校准的零度方向；字形宽高仍必须与当前测量相符。未提供 profile 时保留原右侧文字模型，真实 EDA 使用前必须核对。其他朝向、字形本体、字号或不一致样式需要额外适配，不能通过放宽视觉校验接受未知差异。

## layout.json

完整可运行示例由 `demo` 生成。顶层结构：

```json
{
  "schemaVersion": 1,
  "source": "source.json",
  "measurements": "measurements.json",
  "modules": [{
    "name": "controller",
    "title": "Controller",
    "page": "1",
    "core": "U1",
    "positions": {"U1":[0,0], "C1":[-110,85]},
    "rotations": {},
    "captionOptions": {"_coreLabelY":115},
    "scopes": {"3V3":"global", "GND":"global", "IN1":"page", "OUT1":"page"},
    "wires": [{"net":"3V3", "points":[["U1","3"],[0,110],[-110,110],["C1","1"]]}],
    "stubs": [
      {"ref":"U1", "pin":"1", "length":70},
      {"ref":"U1", "pin":"2", "length":70},
      {"ref":"U1", "pin":"4", "length":25},
      {"ref":"C1", "pin":"2", "length":30}
    ],
    "markers": [{"id":"supply", "kind":"label", "net":"3V3", "point":[-50,110]}],
    "requiredPhysicalPairs": [[["U1","3"],["C1","1"]]]
  }],
  "pages": [{"id":"1", "title":"Main", "widths":[650,800], "maxHeight":2000}]
}
```

这组引脚定义只对应合成示例。用于真实工程时从实际芯片引脚、网表和字体测量生成，不能照搬这些数字。

- `source`、`measurements` 相对 manifest 所在目录解析。模型里的每个元件必须且只能被一个模块分配。
- `name` 和页 `id` 用字母/数字/下划线/连字符，生成目录时拒绝路径穿越。模块名与页 ID 各自唯一。
- `positions` 是目标符号 anchor，允许旋转仅对完成测量、无固定内部文字的双引脚符号开放；其他元件保持原姿态。
- `wires` 是 Agent 制定的显式正交路径，程序做压缩和验证，不自动补齐任意路径。每段只能水平或垂直；连接引脚时必须先沿引脚向外方向走一段。
- 端点支持 `[x,y]`、`["U1","3"]` 或 `{"pin":["U1","3"],"offset":[0,20]}`，后者相对实际变换后的引脚坐标。
- `stubs` 沿引脚实际方向生成短线；GND 自动放接地，其他网生成标签；NC 跳过。
- `scopes` 明确同名标签可连接的范围：`page` / `global`。实际 SDK 是否保留该语义还需现场回读核对。未列出的直接网在本地标签生成后按页局部处理。
- 同名局部网从不同源页迁到同一目标页会被拒绝，需要先核清电气意图；不能仅为了通过检查自动改名或提升全局作用域。
- `requiredPhysicalPairs` 编码“必须真正连线”的引脚对，例如电源去耦、配置电阻、反馈与滤波外围。同名标签不满足这些要求。
- `captionOptions` 支持指定核心文字行 `_coreLabelY`、单元文字行 `_labelY`，或给某个位号指定 `left`；优先保持可读对齐。
- 标题默认按 12 raw 实测并参与模块边界与碰撞检查；page 可用 `titleFontSize` 保留其他字号（1..48 raw），测量文件必须提供该字号的真实标题几何，不能缩字后沿用旧测量。`pages` 决定模块归属和可尝试的画布宽度；不自动平衡电气页归属。
- page 可提供实测 `papers` 比较纸张、可用矩形和图签禁布区，详见[纸张选择](paper-sizing.md)。`packingOrderTrials` 可设为 0..256，额外尝试由固定哈希生成的装箱顺序；默认 0 保留旧的三种顺序，不能由搜索耗尽推断纸张在数学上绝无可行解。
- 模块可选 `variants` 与 `objective`：比较多个位置、允许朝向和路径，先过完整硬约束再评分。字段、示例、报告及局限见[紧凑摆放规则](compact-placement.md)。未提供时保持原有单模板流程。

## 候选与检查输出

`modules/模块名/` 和 `pages/页号/` 都包含 `source.json`、`candidate.json`、`policy.json`、`report.json` 和 `candidate.svg`。顶层 `preview.html` 显示离线页面，`report.json` 汇总面积、线长、拐弯、交叉、重叠等指标。不要只凭面积判断电路质量。

失败时返回退出码 2，保留已生成报告。build 拒绝非空输出目录，防止上次成功报告混入本次失败结果。选择新目录重新计算。

`nativePinTextAllowances` 和 `nativeTextBoundaryAllowances` 只用于已确认的原生固定文字边界接触，按文字 ID/引脚限定并保留证据。原生固定文字的浮点边界例外最大 0.001 raw；不能用它掩盖真实重叠。默认不自动创建例外。

## 电气修复

纯排版模型以源引脚网表为契约。若源图已有短接，应保留 `observed_source.json`，单独建立目标模型和逐引脚变更表，例如 `{ref,pin,before,after,evidence}`，然后以明确目标验证候选。不要重写原快照、原始 SVG 或声称保留了本来就错误的连接。
