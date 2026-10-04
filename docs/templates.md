# 孔板尺寸模板

模板使用 JSON，schema 版本为 1，长度单位固定为 mm。`generic-*` 模板为示意配置；
`nunc-167008` / `nunc-161093` 来自用户提供的厂家尺寸图纸。
数据文件单独存样品信息，不写进几何模板。

| 字段 | 意义 |
|---|---|
| `schema_version` | 整数 `1` |
| `template_id` | 模板标识，如 `brand-catalog-96` |
| `version` | 模板版本，字符串，如 `"1"` |
| `name` | 默认绘图标题 |
| `manufacturer` / `catalog_number` | 厂家与货号，可为空 |
| `units` | 固定为 `"mm"` |
| `rows` / `columns` | 正整数，行数与列数 |
| `width_mm` / `height_mm` | 绘制的板子外框宽度与高度 |
| `well_diameter_mm` | 当前绘制的孔口直径 |
| `well_bottom_diameter_mm` | 可选孔底直径；用于保存数据，当前不参与俯视图绘制 |
| `well_outer_diameter_mm` | 可选孔外径；用于保存数据，当前不参与绘制 |
| `plate_height_mm` / `well_depth_mm` | 可选板高/孔深；保存三维尺寸，当前不参与俯视图绘制 |
| `pitch_x_mm` / `pitch_y_mm` | 横向/纵向孔中心距 |
| `a1_x_mm` / `a1_y_mm` | A1 中心距左/上板边的距离 |
| `corner_radius_mm` | 外框圆角半径；`0` 表示直角 |
| `outline_simplified` | 可选布尔值；外框细节被简化时设为 `true`，输出显示提示 |
| `source.kind` | `illustrative`、`manufacturer` 或 `measured` |
| `source.url` | 来源 URL；厂家模板必填 |
| `source.checked_on` | 非示意模板必须填核验日期，建议 `YYYY-MM-DD` |
| `source.notes` | 来源版本、测量方式、几何简化或其他说明 |
| `source.document_name` / `source.document_sha256` | 可选来源文件名及完整 SHA-256，用于核对原始附件 |
| `source.drawing_number` / `source.drawing_version` / `source.page` | 可选图号、版本和页码，均为字符串 |

孔位从 A1 开始，行向下增加，列向右增加。第 r 行、第 c 列（零起始）的中心：

```text
x = a1_x_mm + c * pitch_x_mm
y = a1_y_mm + r * pitch_y_mm
```

孔口到板边的净距由中心边距减去孔半径得到，不要把两者混用。
尺寸必须来自同一产品、同一几何基准，例如板底 footprint 与上缘尺寸可能不同。
圆角外框是简化俯视图；如厂家有定位缺角，请在 notes 记录当前省略。

使用实际图纸或实测结果修改导出的模板后，可调用：

```python
from plateplot import load_template, draw_plate

template = load_template("my-plate.json")
print(template.center("A1"))
print(template.center("H12"))
draw_plate(template, output="physical.pdf", mode="physical", show_dimensions=True)
```

`source.kind` 是模板提供者的声明。程序只校验结构和几何关系，不声称自动核验了
来源或尺寸；没有得到可靠尺寸的模板应保持 `illustrative`。
当前模板支持规则网格、圆孔和圆角矩形外框，不表示三维制造模型或尺寸公差。

可查阅的官方资料：

- [Corning/Falcon 孔板尺寸表](https://www.corning.com/content/dam/corning/catalog/cls/documents/brochures/CLS-DL-CC-016_REV1_DL.pdf)
- [Thermo Fisher EnduraPlate 96 孔板图纸](https://documents.thermofisher.com/TFS-Assets/LSG/brochures/EnduraPlate_96Well.pdf)
- [Matplotlib 矢量字体输出](https://matplotlib.org/stable/users/explain/text/fonts.html)

仓库只保存自有模板数据和来源链接，不附带厂家原图。
