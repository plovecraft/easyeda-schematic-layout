# EDA 接入与真实结果验收

本 skill 的 CLI 都是离线程序。现场执行使用已经安装的 `easyeda-agent` 或满足相同数据契约的工具；工具不可用时仍可试排，但不能声称已经改好 EDA。

## 安装与连接

`easyeda-agent` 是独立项目。安装来源可从其 skill 的 `metadata.homepage` 核实；当前工作环境使用的来源是 `https://github.com/zhoushoujianwork/easyeda-agent`。使用接收者实际安装版本的环境配置文档，不把本机补丁二进制发给别人。

通常需要安装 CLI/daemon、skill、EDA Agent Connector，开启编辑器“允许外部交互”，打开目标工程原理图。具体菜单与宿主版本兼容性以该版本工具说明为准。

常见只读探测入口：

```text
easyeda --version
easyeda health
easyeda actions
easyeda sch list --help
easyeda sch export-image --help
```

全量读取要包含真实库身份、bbox、pins、wires、page primitives。某些版本可使用：

```text
easyeda sch list --include-device-identity --include-bbox --include-pins --include-wires --include-page-primitives --project PROJECT_UUID --doc DOCUMENT_UUID
```

`PROJECT_UUID` / `DOCUMENT_UUID` 必须从当前连接状态获取。命令不存在或数据不完整时先按该版本 `--help` 适配，不使用旧工程 ID 或把未知当空数据。

## 写入方式

实际链路：Agent/Python 计划 → easyeda CLI → 本地 daemon → EDA Agent Connector → 官方 `eda.*`。

常见连接器 typed actions 包括 `schematic.component.place`、`schematic.component.modify`、`schematic.wire.create`、`schematic.netflag.create`、`schematic.attribute.move`。这些是连接器动作名；官方 SDK 中对应元件和线段的 `eda.sch_PrimitiveComponent.*`、`eda.sch_PrimitiveWire.*` 等接口。以现场 actions/help 为准，不把逻辑候选 JSON 直接当作已支持的 apply payload。

先导出完整工程备份，在候选副本中工作。保留原位号、uniqueId、器件/封装/符号绑定、BOM/PCB 属性和供应商信息。迁移跨页元件时逐个记录 source/target primitive 映射，先验证目标再处理旧对象。

生成原生标签时，本算法约定创建导线时省略隐式 `net` 参数，再创建一个明确的可见 Name 标签，避免 SDK 自动生成中点 Name 后又叠加一份。这个约定必须与工具当前支持的原生行为校准；标签锚点要实际落在线上。

页内与全局标签的作用域、GND 图形和文字基线、原生旋转方向、双引脚旋转以及全工程 PCB 关联都需要现场核对。固定模板只能给布局意图，不能取代器件真实引脚。

同一 EDA 窗口串行写入。超时或部分成功后保留日志，重新读取实际状态，再修计划；不直接重试整批创建。只在目标内容已完整回读后处理旧页或旧对象。

## 保存和验收

1. 明确保存成功，以工具返回 `saved:true` 为证据，不能只看外层 ok 或 autosave。
2. 通过工具重载文档，再取得新的完整快照和原生 SVG。
3. 对新 SVG 运行 `measure`，不修改图形、网名或测量 JSON 来贴合候选。
4. 运行 `verify-native` 检查实际逐引脚/NC/身份、物理连接、线段覆盖、标签/接地位置、所有可见文字与几何。
5. 执行原生连接检查与 DRC，视觉审查实际导图。逐项报告剩余 warning，不把它们隐藏为“全通过”。

`verify-native` 检查的是给定文件，不能从文件推断它一定来自刚保存、刚重载的现场，所以 `nativePersistenceVerified:false` 是有意保留的证据边界。提供现场保存/重载日志才能另外说明持久化。

原生图形验证要求实际符号身份和目标严格一致。SDK 若发生可证实的库 ID 规范化或空元数据补齐，先记录转换和独立来源，再建立新的受控映射；不要放宽比较以接受未知器件。

## 当前不覆盖

本包不执行原始工程文件源码重写、GUI 点击绘图、PCB 布线、制造下单或硬件验证。用户要 PCB/整机功能时由对应工具和流程继续处理，不能把本轮原理图排版报告当作板测结果。
