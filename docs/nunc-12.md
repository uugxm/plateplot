# Nunc 150628 12 孔示意模板

用户同意在缺少精确尺寸图的情况下绘制示意模板。模板 ID 为
`nunc-150628-schematic`，别名为 `cell-culture-12`；数字 `12` 仍选择 `generic-12`。

## 厂家信息与示意假设

[厂家产品页](https://www.thermofisher.com/order/catalog/product/jp/ja/150628)
确认货号 150628、3×4 圆孔平底排列、每孔培养面积 3.5 cm²、工作体积 2 mL、
透明 PS 材质与 Nunclon Delta 处理。
[厂家 Microplates Guide](https://assets.thermofisher.com/TFS-Assets/LCD/Product-Guides/Superior-performance-Microplates-Guide-CTLSPPLATEGUIDE-EN.pdf)
印刷第 11 页列出外形 128×86 mm。这是目录名义尺寸，不表示精确工程尺寸或公差。
资料核验日期：2026-10-05。未找到可以确认对应 150628 的厂家尺寸图。

| 绘制参数 | mm | 依据 |
|---|---:|---|
| 板长 / 板宽 | 128 / 86 | 厂家目录名义尺寸 |
| 示意孔直径 | 22 | 沿用 generic-12 的示意选择，非厂家确认孔口尺寸 |
| 横 / 纵孔中心距 | 26 / 26 | 示意选择，未实测 |
| A1 距左 / 上边框 | 25 / 17 | 居中假设：(128−3×26)/2、(86−2×26)/2 |
| 外框圆角 | 0 | 简化直角轮廓，省略真实缺角、圆角和筋条 |

孔边到左右框净距为 14 mm，上下为 6 mm，均由上述示意参数计算。
没有从照片测量，也没有用培养面积反推孔口直径。模板不保存未确认的孔底直径、
板高或孔深。`source.kind` 保持 `illustrative`，五项孔径/孔距/位置字段列在
`assumed_fields` 中；CLI 提示与 SVG/PDF 元数据保留示意性质，图面默认隐藏参数。
文件中的标尺对应模板坐标中的 10 mm，不代表未知几何已获得实物校准。

## 绘制与替换尺寸

```bash
plateplot draw --template cell-culture-12 --labels well --font-size 16 --output twelve.svg
plateplot draw --template cell-culture-12 --labels well --font-size 16 --output twelve.pdf
plateplot export-template cell-culture-12 twelve-template.json
```

图中沿用板内 16 pt 行列编号、0.85 pt 孔边线、板内 10 mm 标尺，默认不显示板名、
参数和页脚。孔内文字、填色与浓度使用现有 API/CSV 数据功能。
获得同型号厂家图纸或实测尺寸后，更新导出的 JSON、来源说明及 `assumed_fields`。
本模板适合实验布局示意，不用于精密实物定位。
