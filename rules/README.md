# 规则库

此目录保存由《电子科技大学成都学院毕业论文（设计）撰写格式规范》（附件1）、相关表格（附件2）和撰写示范（附件3）整理出的 JSON 规则。

规则文件使用 `schema_version`、`name`、`source` 和 `checks`。每个检查项包含唯一 `id`、检测器 `type`、可选 `target`、`expected` 期望值和可选 `enabled` 开关。

### source：规范来源（必填建议）

`source` 说明这套 `checks` 依据哪份文件的哪些条款，是 PDF 报告「检测依据」章节与 `/api/v1/report/create` 响应中 `rule_source` 的唯一数据来源：

```json
"source": {
  "title": "规范全称",
  "document": "附件1：……撰写格式规范.docx",
  "organization": "发布单位",
  "scope": "本科毕业论文（设计）",
  "clauses": [
    {
      "id": "body",
      "title": "正文主体与章节标题",
      "chapter": "三、论文排版（一）正文部分",
      "text": "条款摘要原文……",
      "rules": ["body-font", "body-size"],
      "automated": true
    }
  ],
  "notes": ["仅供人工核对的提示"]
}
```

- `clauses[].rules` 用**规则 id** 声明该条款由哪些检查项实现，全部启用的检查项都应被某条条款引用（`unmapped_rule_ids()` 为空），否则报告里的条款覆盖情况会失真。
- `automated: false` 表示规范有要求但机器不判定（如字数、查重率），报告中会归入「人工核对提示」。
- 旧写法里 `source` 可以是只写文件名的字符串，加载时会自动转成对象（`title` 取规则集名称）。

当前 `default.json` 的条款全部来自《电子科技大学成都学院毕业论文（设计）撰写格式规范》（附件1）及其四张排版表（文首部分、正文部分、文尾部分、纸张规格），本身不引用附件2（教务表格）与附件3（撰写示范）的内容。

## 规则集注册表（目录扫描 + 可配置）

`rules/` 下的每个 `*.json` 都是一个可独立选择的规则集，由 `backend.app.rules.registry` 扫描登记：

| 配置项 | 环境变量 | 默认值 |
| --- | --- | --- |
| 规则目录 | `PAPER_RULES_DIR` | 仓库根 `rules/` |
| 默认规则集 | `PAPER_RULES_DEFAULT` | `default` |

- **id 解析**：优先取文件里的 `rule_set_id`，缺省回退到文件名（不含扩展名）。
- **可选列表**：`GET /api/v1/rule/list`，单项详情 `GET /api/v1/rule/{rule_set_id}`。
- **单次检测指定**：`POST /api/v1/detect/start` 传 `rule_set_id`；不传则用 `PAPER_RULES_DEFAULT`。任务会记住所用规则集（`TaskRecord.rule_set_id`），报告据此复述「检测依据」。
- 新增一个学校的规范只要往目录里放一个 JSON 即可，无需改代码；`_`-/`.`-开头的文件与 `*.schema.json` 不参与扫描。
- 单个文件损坏时只在列表中标记 `loadable=false` 与 `error`，不会拖垮整个目录（测试 `test_every_repo_rule_file_is_loadable` 会守住「仓库内不允许有坏文件」）。

已登记的规则集：

| id | 文件 | 说明 |
| --- | --- | --- |
| `default` | `default.json` | 现行唯一规则集，含 92 项检查与 `source.clauses` 条款追溯 |

> 旧版 `electronic-tech-cdu-v1.json` 已删除，不再维护；现行规则一律写在 `default.json`。
> 加载器仍保留对旧结构（`page`/`body`/`headings`/`manual_checks`，没有 `checks` 字段）的翻译能力，
> 便于直接接入历史格式的文件：`manual_checks` 会落到 `source.notes` 作为人工核对提示。

加载、校验和执行入口为 `backend.app.rules.loader.load_rules`、`backend.app.rules.registry` 与 `backend.app.rules.service.check_document`。

## 自动检测项

当前支持的检测器：`font`、`size`、`bold`、`alignment`、`line_spacing`、`paragraph_indent`、`paragraph_spacing`、`page_margin`、`heading_numbering`、`toc_consistency`、`table_figure_format`、`reference_baseline`、`required_sections`、`keyword_format`、`caption_format`、`header_text`。

`default.json` 覆盖的学校规范包括：

- 页面：A4（21×29.7cm），页边距上/下 3.5cm、左/右 3.0cm，页眉 2.75cm、页脚 1.75cm
- 正文（含中文摘要、结论、致谢、附录正文）：宋体小四、两端对齐、首行缩进 2 字符、固定值 20 磅、段前 6 磅、段后 0 磅
- 标题：第1章黑体小三居中 30/30；1.1 黑体四号顶格 18/18；1.1.1 / 1.1.1.1 黑体小四，12/12 与 6/6
- 文首文尾标题：摘要/参考文献/致谢/附录/结论为黑体小三居中；ABSTRACT 为 Times New Roman 小三；目录标题为宋体小二（不是黑体小三）
- 英文摘要正文：Times New Roman 小四、首行缩进 1 字符、固定值 20 磅
- 关键词：3–8 个、分号分隔、末尾无标点；英文 Keywords 小写（出现时检查，专科论文不强制英文摘要）
- 参考文献条目：宋体五号、悬挂缩进 1 字符、固定值 17 磅、段前 3 磅
- 图/表题：宋体五号居中；图题段前 6/段后 12，表题段前 12/段后 6
- 必备结构：摘要、目录、参考文献、致谢
- 偶数页眉包含「电子科技大学成都学院本科毕业论文」
- 标题编号连续性（含「第N章」）与目录/参考文献序号基线

规则引擎只依据解析后的内存 `Document` 运行。字号可用 pt 或中文字号（如 `小四`），缩进可用 pt 或「字符」并优先采用 DOCX 原始字符缩进；对缺失的格式信息不报错。图表列数等约束只有显式配置 `table_figure_format` 才会执行，默认规则不启用该项。

## 人工核对项（不做自动误杀）

附件2教务表格、封面模板、签名日期、装订顺序、查重率、分专业字数等无法从正文 DOCX 稳定判定，保持人工核对，不写入自动 `checks`：

- 封面、任务书、进度计划表、开题报告、初期/中期检查表、指导教师/评阅/答辩/成绩考核表、学术诚信声明、版权使用授权书、封底
- 装订顺序、双面印刷、奇偶页页眉是否与当前章题一致
- 查重率不高于 25%（学院可更严）
- 字数：工科/艺术设计类设计型不少于 8000 字，论文型及理科不少于 10000 字，人文社科不少于 12000 字
- 外文资料原文与译文、公式编号位置、量和单位全文统一
- 参考文献著录内容是否符合《中国高校自然科学学报编排规范》

复杂目录域、中文数字编号和嵌入 Excel 图表仍需人工核对或后续增强。
