# 1.1.0 验证范围

单元测试仅使用程序生成的合成数据。另附用户明确授权的新建独立[公开测试工程](../examples/robot-controller/README.md)，提供原生工程、实际导图和前后对比；此前私人项目不在包内。

## 合成示例

`scripts/layout_engine/demo.py` 构造 6 个通用符号、21 个虚构引脚并生成三页教学图。符号、位号和网络均为演示定义，不对应真实产品。

## 可复现检查

```bash
python scripts/layout.py demo --out ./layout-demo
python scripts/layout.py check-preview --input ./layout-demo/result/preview.html --out ./layout-demo/preview-check.json
python -m unittest discover -s tests -v
```

57 项测试覆盖错网短接、缺失物理直连、NC、文字重叠、器件身份、出线方向、受支持的总线修复、矩形装箱、确定性重算、多模块同页、局部网络作用域、跨页模型合并、原生少线/多线/标签重复、线段拆分与文件校验边界。新增测试验证接地文字样式校准、输入不可变、不一致样式和未校准朝向拒绝。原生回读测试同样使用合成快照，不需要个人工程。

新增 13 项候选比较测试：不同朝向胜出、合法低折返路径、非法紧凑方案、物理直连、输入不可变、确定性、字段权限、权重/数值/目录边界与全失败报告。可运行 `python scripts/layout.py demo --compare-placements --out ./placement-demo` 复现。

另外检查 skill 格式、Python 编译、文档链接、隔离安装、已有安装不被覆盖、ZIP 校验和及分享文件白名单。

## 运行环境与限制

在 Windows、Python 3.12、Node.js 24 下执行；浏览器依赖精确版本见 `scripts/package-lock.json`。未验证其他系统实机、所有 EDA 版本/字体/符号、打印纸张边界、PCB 制造或硬件功能。公开报告分别标注合成测试与独立真实库示例；不包含此前私人项目记录。

## 独立试用与文字几何

独立试用对 25 个自建候选、8 类故障注入及重复构建作检查。初次发现 standalone validate 接受 bbox 缩小、translation 不一致及字号缩小，现已修正，三个保存反例均被拒绝；正常重建与预览复测通过。新增 5 项回归覆盖上述 3 项文字完整性、原生图框分类、框与标题的刚性平移。

validate 对原生文字的尺寸/平移与保留源对账，但源 JSON、SVG 及字体测量仍须可信；它不是任意外部 SVG 的真实性鉴定器。实际导图必须重新实测。自带 invalid-overlap 候选可能先因非正交路径拒绝，仅证明其非法；器件/文字重叠由专门的故障注入覆盖。

标准单元 fixture 使用未加 --compare-placements 的 demo；比较 demo 是独立行为示例。

纸张比较新增 8 项回归，覆盖最小可用纸、过小纸拒绝、图签禁布、框/标题平移、几何来源、浮点尾差网格化及整体居中。独立试用验证 256 次装箱顺序重算一致，非法预算拒绝；可用区仍是保守矩形，不搜索一般不规则剩余空间。离线预览按内容裁切，完整纸张与标题栏以实际 EDA 导图验收。

新增标题字号保留回归覆盖独立装箱及带纸张装箱，测量字号不匹配时拒绝；本次真实对比保留 20 raw 功能标题。完整新建小车比较采用仅 EDA skill 的独立真实基线，见 [方法与逐页结果](../examples/robot-controller/README.md)。
