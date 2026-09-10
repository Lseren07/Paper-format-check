# 规则库

此目录用于保存由学校格式规范、相关表格和论文示范文档整理出的 JSON 规则。

规则文件使用 `schema_version`、`name` 和 `checks`。每个检查项包含唯一 `id`、检测器 `type`、可选的 `target`、`expected` 期望值和可选的 `enabled` 开关。

当前支持的检测器：`font`、`size`、`bold`、`alignment`、`line_spacing`、`paragraph_indent`、`heading_numbering`、`toc_consistency`、`table_figure_format`、`reference_baseline`。

规则引擎只依据解析后的内存 `Document` 运行。字号规则可使用 pt 或中文字号（如 `小四`），首行缩进规则可使用 pt 或“字符”单位（如 `2字符`），并优先采用 DOCX 的原始字符缩进值；对缺失的格式信息不报错。标题连续性覆盖阿拉伯数字的单级和多级标签（如 `1.`、`1.2`），目录比对会忽略末尾页码。默认规则覆盖页边距；图表规则必须显式配置列数等约束才会执行，不读取嵌入 Excel 数据；复杂目录域和中文数字编号仍需人工核对或后续增强。
当前规则库统一使用 `default.json`。规则加载、校验和执行入口为
`backend.app.rules.loader.load_rules` 与 `backend.app.rules.service.check_document`；旧的
`electronic-tech-cdu-v1.json` 和 `backend.app.services` 入口不再作为规则实现。

规则文件按学校规范区分自动检测项和人工核对项；封面、学校表格填写、复杂目录一致性、图表和参考文献著录等仍可能需要人工或后续深度检测。
