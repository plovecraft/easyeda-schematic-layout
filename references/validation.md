# 1.0.2 验证范围

公开验证材料只使用程序生成的合成数据，不收录用户工程、原始图纸、专用模板、截图、回读日志或真实工程统计。

## 合成示例

`scripts/layout_engine/demo.py` 构造 6 个通用符号、21 个虚构引脚并生成三页教学图。符号、位号和网络均为演示定义，不对应真实产品。

## 可复现检查

```bash
python scripts/layout.py demo --out ./layout-demo
python scripts/layout.py check-preview --input ./layout-demo/result/preview.html --out ./layout-demo/preview-check.json
python -m unittest discover -s tests -v
```

31 项测试覆盖错网短接、缺失物理直连、NC、文字重叠、器件身份、出线方向、受支持的总线修复、矩形装箱、确定性重算、多模块同页、局部网络作用域、跨页模型合并、原生少线/多线/标签重复、线段拆分与文件校验边界。新增测试验证接地文字样式校准、输入不可变、不一致样式和未校准朝向拒绝。原生回读测试同样使用合成快照，不需要个人工程。

另外检查 skill 格式、Python 编译、文档链接、隔离安装、已有安装不被覆盖、ZIP 校验和及分享文件白名单。

## 运行环境与限制

在 Windows、Python 3.12、Node.js 24 下执行；浏览器依赖精确版本见 `scripts/package-lock.json`。未验证其他系统实机、所有 EDA 版本/字体/符号、打印纸张边界、PCB 制造或硬件功能。公开报告仅说明合成示例和软件测试，不包含私人项目验证记录。
