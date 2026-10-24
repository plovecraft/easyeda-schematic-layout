---
name: easyeda-schematic-layout
description: 根据真实元件、引脚与 SVG 文字边界，使用功能模板、标签避让和矩形装箱紧凑整理嘉立创 EDA 原理图，并独立检查连接、NC、短接和版面。适用于原理图太乱、标签重叠、多页整理、统一绘图风格与排版算法复用；实际编辑需可用的 EDA 接口。不负责 PCB 自动布线。
metadata:
  version: "1.0.2"
---

# 原理图排版与校验

把用户认可的画法转为功能模板，用确定性几何算法生成并检查离线候选，再通过可用 EDA 接口落成可编辑工程。保留器件身份和电气意图；需要修短接时单独记录电气变更，不能把现有短接当作正确网表保留。

## 按任务读取

- 安装、演示和使用：[README.md](README.md)。程序、依赖、具体算法：[技术说明](references/software-and-algorithms.md)。
- 处理自己的工程或写模板前：[数据契约](references/data-contract.md)。
- 连接、写入或最终验收前：[EDA 接入](references/eda-integration.md)。现场操作同时遵守已安装 `easyeda-agent` 的当前接口说明；离线演示不需要该依赖。

## 工作方法

1. 保留完整原生快照、SVG、引脚与网络。在 `raw / Y-up` 坐标中计算，保留实际半网格引脚；缺失或歧义数据先补齐。
2. 沿用用户确定的分页与风格；没有约定时按功能组织芯片、外围、标签与跨模块网络。紧凑不能破坏功能归属。
3. 根据实际电路创建 `layout.json`：位置、允许旋转、正交路径、向外短线、标签作用域、`requiredPhysicalPairs`。模板由 Agent 制定，本包没有任意电路全自动布局/布线入口。新器件先用小模块验证几何。
4. 用 `scripts/layout.py build` 完成位号/参数候选搜索、接地位置搜索、原生标签避让与模块装箱。无解时看报告、修模板、重算，不能关闭检查换取通过。
5. 审查预览和独立报告。引脚先沿自身向外方向引出，再转弯或分支；保留正交线，减少多余折返。所有可见文字参与检查，必需的外围直连不能由同名标签代替。
6. 已授权编辑且连接可用时，通过现有 EDA 工具串行写入候选副本；保存、重载、重新读取、导出 SVG，运行 `verify-native`，完成原生 DRC 与视觉审查。超时或部分成功先回读，不重放未知状态的写操作。

## 快速入口

从本 skill 根目录运行，使用环境实际可用的 Python：

```bash
python scripts/layout.py doctor
python scripts/layout.py demo --out ./layout-demo
python scripts/layout.py build --manifest ./work/layout.json --out ./candidate-r1
python scripts/layout.py validate --source ./source.json --candidate ./candidate.json --policy ./policy.json --out ./check.json
```

演示与 build 均为离线操作，不连接或改动 EDA。

## 必须保留的约束

- 纯排版保留 `uniqueId`、库资产、封装、值、引脚、网名和 NC。跨页重建需要身份映射及 PCB 关联检查。
- 原始观测、目标网表、候选和实际回读分别保存。电气修复记录原网络、目标网络与依据，不改写原始导出或测量结果。
- 文字边界来自本地浏览器对原生 SVG 的 `getBBox()`。缺字体先处理，不能用字符数估计冒充实测。基线与固定引脚文字接触只允许明确、有限、留痕的例外。
- 新工程先核对 GND 文字样式；不同于默认模型时用 `calibrate-ground` 读取至少两个原生样本，在派生测量文件中提供 `nativeGroundLabelProfile`。不改原始导图或测量来掩盖差异。
- `conform` 仅自动处理同向垂直引脚接水平总线这一类情况；其他情况修模板。
- Python 不使用 `-O`。离线通过、真实回读通过、保存重载、DRC 和硬件验证分别报告。未验证纸张尺寸时标明自由画布。

交付预览、候选、策略、检查报告和可复现命令。用户只要求讨论或离线试排时保持该范围。

公开分享仅包含通用算法、说明与合成示例，按 `SHARE_FILES.json` 白名单生成包；不加入用户工程、专用模板、网表、截图、回读日志或真实项目统计。
