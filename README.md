# 原理图排版与校验 Skill · 1.0.1

包含可安装的 skill、实际 Python 算法、中文技术说明和独立三页示例。Agent 根据电路制定功能模板，程序完成几何计算与检查，真实 EDA 读写通过 `easyeda-agent` 及其连接器执行。

## 安装 skill

解压 ZIP，进入 `easyeda-schematic-layout` 文件夹，保留整个文件夹：

```powershell
python scripts/install_skill.py
```

默认安装到 `$CODEX_HOME/skills/easyeda-schematic-layout`；未设置 `CODEX_HOME` 时用用户主目录下 `.codex/skills/easyeda-schematic-layout`。安装器验证校验清单，不联网、不覆盖已有 skill。也可手动把整个目录复制到该位置。

下一轮输入可调用；若客户端尚未刷新 skill 列表，重新打开对话或重载客户端：

```text
使用 $easyeda-schematic-layout，跑自带三页示例，打开预览并说明检查结果。
```

其他支持目录式 skills 的客户端可手动安装到其对应目录；本包只提供 Codex 自动安装入口。

## 安装程序依赖

进入**实际安装后的 skill 文件夹**，以下命令都从该目录运行。`python` 可换成环境可用的 `python3` 或 `py -3`。

```powershell
python -m pip install -r requirements.txt
npm install --prefix scripts
python scripts/layout.py doctor
```

需要 Python 3.10+、lxml、Node.js、Playwright 和 Chrome/Edge/Chromium。Python 核心算法只依赖 lxml；文字实测、示例生成和截图需要浏览器。Node.js 至少使用 18，具体还需满足当前安装的 Playwright 所要求的引擎版本。

脚本优先找系统浏览器；找不到时安装 Playwright Chromium：

```powershell
cd scripts
npx playwright install chromium
cd ..
```

或通过 `SCHEMATIC_BROWSER` 指定浏览器执行文件。Linux 按 Playwright 提示补齐系统库。新增标签使用 Arial 测量；缺字体时有替代风险，应在同一字体环境测量实际 EDA 输出并核对。

`doctor` 只检查依赖，不启动 EDA。模块存在不等于浏览器可启动，以 demo 实际运行为准。

## 跑独立示例并测试

使用尚不存在或为空的输出目录：

```powershell
python scripts/layout.py demo --out ./layout-demo
python scripts/layout.py check-preview --input ./layout-demo/result/preview.html --out ./layout-demo/preview-check.json
python scripts/layout.py render --input ./layout-demo/result/pages/1/candidate.svg --out ./layout-demo/page1.png
python -m unittest discover -s tests -v
```

打开 `layout-demo/result/preview.html`。`layout-demo/layout.json` 是可修改的完整模板；逐页 `candidate.json`、`candidate.svg`、`policy.json` 和 `report.json` 位于 `result/pages/1..3/`。

演示有 6 个合成元件、21 个引脚，用于验证安装和算法流程。三个教学模块沿用同一简化结构，不代表三种经过电气验证的真实电路。它不含厂商元件库，也不写入 EDA。

测试默认读取 `layout-demo`；可用 `SCHEMATIC_TEST_DEMO` 指定别的演示目录。测试在临时目录中做故障注入，不修改真实工程。

## 用在自己的工程

现场读写需要嘉立创 EDA、`easyeda-agent` skill/CLI/daemon 和 EDA Agent Connector。版本与安装以该工具当前文档为准；本包没有内置或自动更新这些组件。`design-hardware` 可辅助设计取舍，离线排版不强制依赖它。

可以直接对 Agent 说：

```text
使用 $easyeda-schematic-layout 整理当前原理图。
保留电气连接，按“主控与接口 / 电源 / 按键与灯光”三页组织。
芯片外围分组，标签对齐，布局紧凑，引脚先向外引出再转弯。
先生成离线预览和检查报告，我认可后再写入候选工程。
```

若已经授权直接编辑，可明确“完成候选后直接写入副本并保存、重载、回读检查”。分页数量由任务决定，三页只是示例。

手动命令如下，数据字段见 [数据契约](references/data-contract.md)，现场步骤见 [EDA 接入](references/eda-integration.md)：

```powershell
python scripts/layout.py measure --input ./work/native.svg --texts ./work/extra_texts.json --out ./work/measurements.json
python scripts/layout.py import --snapshot ./work/snapshot.json --svg ./work/native.svg --measurements ./work/measurements.json --out ./work/source.json
python scripts/layout.py build --manifest ./work/layout.json --out ./candidate-r1
```

`snapshot.json` 与 `native.svg` 来自真实 EDA；`extra_texts.json` 包含全部网名和标题；`layout.json` 由 Agent 根据真实电路建立，可参考 demo 的格式。

多张源页先各自测量、导入，再合并。合并只重命名内部模型/SVG ID，保留真实 `native` 身份：

```powershell
python scripts/layout.py combine --models ./p1/source.json ./p2/source.json --measurements ./p1/measurements.json ./p2/measurements.json --out ./combined
```

本包**没有独立的一键 apply 命令**。Agent 用现有 EDA 工具将候选落实成原生元件、导线、标签和标题；不同版本接口、跨页迁移和保存由该工具适配。

保存、重载后重新导出完整快照和 SVG，再测量并核对实际结果：

```powershell
python scripts/layout.py verify-native --snapshot ./actual/snapshot.json --candidate ./candidate-r1/pages/1/candidate.json --policy ./candidate-r1/pages/1/policy.json --svg ./actual/native.svg --measurements ./actual/measurements.json --out ./actual/verification.json
```

`verify-native` 不自行保存或重载，因此其 `nativePersistenceVerified` 仍为 false；保存成功、重载和重新读取需要另外的 EDA 工具日志证据。

## 程序、算法和能力边界

详见 [程序与算法](references/software-and-algorithms.md)：逐项列出运行程序、依赖、算法、对应源码和局限。

算法依靠功能模板、局部几何搜索和矩形装箱，不提供通用 A* 自动布线入口。

只自动旋转完成测量、无固定内部文字的双引脚符号。镜像、特殊总线、层次端口和复杂多单元器件需要额外适配。原生 GND 图形按这次校准的 21 raw 宽度处理，换版本/字体/图形后需重新核对。

检查不代表电路设计正确、PCB 可制造或硬件功能通过；自由画布也不代表 A4/A3 打印范围已经检查。具体测试见 [验证记录](references/validation.md)。

## 分享

分享整个 ZIP 即可。文件按 `SHARE_FILES.json` 固定白名单收录，仅包含通用算法、文档和合成教学示例；不含真实项目名称、专用电路模板、网表、器件选型、截图、回读日志、工程统计、本机路径、账号或浏览器会话。第三方依赖另行安装。

`CHECKSUMS.sha256` 用于核对意外损坏，不是数字签名。安装器只复制该清单所列文件，不带走本地依赖或试验输出。修改后分发应更新校验清单并记录新版本。
