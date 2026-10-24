---
name: schematic-layout-optimizer
description: 根据真实元件、引脚与 SVG 文字边界，使用功能模板、标签避让和矩形装箱紧凑整理嘉立创 EDA 原理图，并独立检查连接、NC、短接和版面。适用于原理图太乱、标签重叠、多页整理、统一绘图风格与排版算法复用；实际编辑需可用的 EDA 接口。不负责 PCB 自动布线。
metadata:
  version: "1.1.1"
  author: "plovecraft"
  license: "AGPL-3.0-only"
---

# 原理图排版与校验

Copyright (C) 2026 plovecraft。原创内容按 [AGPLv3](LICENSE) 授权；范围与第三方保留见 [COPYRIGHT.md](COPYRIGHT.md) 和 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

把用户认可的画法转为功能模板，用确定性几何算法生成并检查离线候选，再通过可用 EDA 接口落成可编辑工程。保留器件身份和电气意图；需要修短接时单独记录电气变更，不能把现有短接当作正确网表保留。

## 按任务读取

- 安装、演示和使用：[README.md](README.md)。程序、依赖、具体算法：[技术说明](references/software-and-algorithms.md)。
- 处理自己的工程或写模板前：[数据契约](references/data-contract.md)。减少折返、比较元件位置与朝向时读[紧凑摆放规则](references/compact-placement.md)。
- 页面太空、纸张过大或恢复图签时读[纸张选择](references/paper-sizing.md)，依据实测可用区选择较小的合适尺寸，并将整体布局居中于扣除图签的可用区域。
- 连接、写入或最终验收前：[EDA 接入](references/eda-integration.md)。现场操作同时遵守已安装 `easyeda-agent` 的当前接口说明；离线演示不需要该依赖。

## 工作方法

1. 保留完整原生快照、SVG、引脚与网络。新放置元件先保存重载再取基线，避免宿主稍后补配 uniqueId。在 `raw / Y-up` 坐标中计算，保留实际半网格引脚；缺失或歧义数据先补齐。
2. 沿用用户确定的分页与风格；没有约定时按功能组织芯片、外围、标签与跨模块网络。紧凑不能破坏功能归属。
3. 根据实际电路创建 `layout.json`：位置、允许旋转、正交路径、向外短线、标签作用域、`requiredPhysicalPairs`。先尝试移动/旋转元件使连接轴线对齐，再安排最少必要转弯；不要先固定松散位置再用台阶补偿。模板由 Agent 制定，本包没有任意电路全自动布局/布线入口。新器件先用小模块验证几何。
4. 需要优化时为模块提供 `variants`，比较保持原状与若干位置/允许朝向；每个方案重新计算实际引脚、文字和路径。通过全部硬约束后，按面积、折点、线长和交叉评分，再进行模块装箱。任何元件都不预设必须横放或竖放，不能靠缩小字号、删标签或放松检查制造紧凑。无解时修模板重算。
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
- 沿用原有图框、标题栏及字段；依据实测纸张与图签禁布区装箱。不能为获得自由画布而默认删图框。实际导图同时检查图签文字；字段值和纸张边界另从原生接口回读。

交付预览、候选、策略、检查报告和可复现命令。用户只要求讨论或离线试排时保持该范围。

公开分享按 `SHARE_FILES.json` 白名单生成包。通用代码、合成示例和用户明确授权的独立公开测试工程可收录；现有私人项目不随之获得公开授权。发布前检查账号元数据、本机路径、原有项目和截图内容，包括原生 Logo 中递归嵌入的 SVG 联系信息。仅清理分享副本，保留原始观测供验证，并核对清理未改变可见图形或电气记录。包内独立公开测试见 [示例说明](examples/robot-controller/README.md)。
