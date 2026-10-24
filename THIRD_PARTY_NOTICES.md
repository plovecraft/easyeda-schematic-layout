# 第三方依赖与素材说明

本项目版权声明和 AGPL 授权仅涵盖有权授权的原创部分。以下第三方组件或素材保留其原有版权、许可和商标权；本说明不替它们授予额外权利。

## 单独安装的运行组件

| 组件 | 用途 | 许可或来源 |
|---|---|---|
| Python | 运行排版、校验与安装脚本 | [Python 许可](https://docs.python.org/3/license.html)；解释器不随包分发 |
| lxml | 读取和处理 XML / SVG | [lxml 版权与许可](https://lxml.de/copyright.html)；其底层库按相应发行物中的条款执行 |
| Node.js | 运行浏览器辅助程序 | [Node.js LICENSE](https://github.com/nodejs/node/blob/main/LICENSE)；运行时不随包分发 |
| Playwright / playwright-core | SVG 文字实测、预览与截图 | Apache-2.0，见 [Playwright LICENSE](https://github.com/microsoft/playwright/blob/main/LICENSE)；精确版本见 `scripts/package-lock.json` |
| Chrome / Edge / Chromium 及字体 | 本地 SVG 渲染 | 各自发行物和字体许可；浏览器、字体不随包分发 |
| easyeda-agent、EDA Agent Connector 与嘉立创 EDA | 可选的原生工程读写 | 分别按工具或服务当前发布的许可及条款执行；本包不捆绑这些组件。工具来源见 [easyeda-agent](https://github.com/zhoushoujianwork/easyeda-agent) |

`requirements.txt`、`scripts/package.json` 和锁文件是依赖声明，不表示将依赖重新许可为 AGPL。安装、使用或另行分发这些组件时，应遵守其自身条款并保留相应通知。

## 独立公开测试中的库素材

`examples/robot-controller/` 包含明确获准公开的新建测试工程、原生读回、SVG 和截图。其中真实器件库的符号、封装、器件属性、供应商标识，以及原生图框中的 Logo 或其他既有素材，来源于相应 EDA 库或厂商，原有权利保留。plovecraft 的声明覆盖原创程序、模板、连线编排和对比说明，不主张这些第三方素材的所有权，也不替代其许可。

器件核对资料包括 [ST STM32F103x8/B](https://www.st.com/resource/en/datasheet/stm32f103c8.pdf)、[TI TPS54302](https://www.ti.com/lit/ds/symlink/tps54302.pdf) 和 [Diodes AP2112](https://www.diodes.com/assets/Datasheets/AP2112.pdf)。数据手册仅作为来源链接，完整手册不随本包分发。

商标和 Logo 的出现仅用于保留原生输出及说明兼容性，不表示原权利人背书、授权使用其品牌，或对本例作出电气与硬件验证。

## 许可证文本来源

`LICENSE` 为 GNU AGPL 第 3 版的完整原文。官方说明：[GNU AGPLv3](https://www.gnu.org/licenses/agpl-3.0.html)；本次文本取自 [SPDX 的 AGPL-3.0-only 标准文本](https://github.com/spdx/license-list-data/blob/main/text/AGPL-3.0-only.txt)，保留 Free Software Foundation 的原始版权声明。
