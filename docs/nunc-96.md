# Thermo Scientific Nunc 167008 / 161093

这两款是 Nunc MicroWell 96 孔 Nunclon Delta 处理平底板，模板分别为
`nunc-167008` 和 `nunc-161093`。几何共用，包装货号分别保存。

## 尺寸来源

- 用户提供的 `Technical Data Sheet- 167008 and 161093.pdf`，第 1 页。
- 图纸标题：MicroWell plate F96 / Straight plate。
- 图号 `2817`，版本 `10`，生效日期 `2007-05-31`；核对日期 `2026-10-05`。
- PDF SHA-256：`a042684dec585378c7772da1cee73c391e43825450c2e9b561ebc1657114c122`。
- 产品身份链接：[167008](https://www.thermofisher.com/order/catalog/product/167008)、
  [161093](https://www.thermofisher.com/order/catalog/product/161093)。这些是产品页，
  具体尺寸依据上述附件的图纸，不能将产品页当作尺寸图纸。

仓库保存尺寸数据与文件指纹，不复制厂家 PDF 或图纸截图。

## 名义尺寸（mm）

| 项目 | 名义值 | 图纸标注/说明 |
|---|---:|---|
| 板底外框长度 | 127.76 | ±0.25 |
| 板底外框宽度 | 85.48 | ±0.25 |
| 板高 | 14.4 | +0.2 / 0.0；不含盖 |
| 孔口内径 | 6.97 | ±0.10；D 详图靠孔口端 |
| 孔底内径 | 6.17 | ±0.10；D 详图靠孔底端 |
| 孔外径 | 8.4 | D 详图；不用于孔内填色范围 |
| 孔深 | 11.4 | +0.0 / -0.2 |
| 横/纵孔中心距 | 9 / 9 | 图纸框注基本尺寸，横向 11 个间隔、纵向 7 个间隔 |
| 左边至第 1 列中心 | 14.3 | 框注基本尺寸，基准 A |
| 下边至 H 行中心 | 11.3 | 框注基本尺寸，基准 B；不是 A 行到上边的距离 |

图纸对孔位另有 `96x`、位置度 `⌀0.5`、基准 `A-B` 的标注。
框注基本尺寸不直接套用页脚的一般线性尺寸公差。模板用于名义布局，不把公差画成孔的尺寸变化。

## 左上角坐标系的换算

```text
A1_x = 14.3
H1_y = 85.48 - 11.3 = 74.18
A1_y = H1_y - 7 * 9 = 11.18
A12_x = 14.3 + 11 * 9 = 113.3
right_center_margin = 127.76 - 113.3 = 14.46
```

孔口半径是 `6.97 / 2 = 3.485 mm`。由此计算孔口到外框的净距：
左侧 `10.815 mm`、上侧 `7.695 mm`、右侧 `10.975 mm`、下侧 `7.815 mm`。
上下、左右边距并不完全相等，不能使用居中网格自动补全它们。

## 外框简化

外框使用图纸的板底 footprint 尺寸。图纸显示圆角、内台阶、定位/模具标记及局部倒角，
但本模板不从图片像素比例推算这些轮廓。`corner_radius_mm=0` 是绘图简化值，
并不声称实物圆角半径为零；`outline_simplified=true` 会在 CLI 中提示，
开启 `--show-parameters` / `show_parameters=True` 时也会显示在图底。
页脚未定义半径 R0.20 mm 没有用于推断肉眼可见的整体外框圆角。

俯视填色圆使用孔口内径 6.97 mm，孔底内径、孔外径、板高及孔深作为独立元数据保存。
所有值是本版本图纸的名义尺寸，实际制造尺寸按图纸公差。

## 使用

```bash
plateplot draw --template nunc-167008 --data examples/samples-96.csv --output output/nunc.svg
plateplot draw --template nunc-161093 --mode physical --dimensions --output output/nunc.pdf
```

```python
from plateplot import load_template, draw_plate

plate = load_template("nunc-167008")
assert plate.center("A1") == (14.3, 11.18)
draw_plate(plate, data="examples/samples-96.csv", output="nunc.svg")
```
