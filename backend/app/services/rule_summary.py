"""把规则库的来源规范（`rules.source`）整理成报告与接口可直接使用的摘要。

这里的每一条内容都来自 rules JSON 中的 `source` 块，而 `source` 块是对学校
规范原件（《电子科技大学成都学院毕业论文（设计）撰写格式规范》，附件1）的条款化提炼，
因此报告里不能再出现「依据实际加载的规则文件」这类占位说法。

每个条款通过 `rules` 字段声明它实现了哪些检查项（按 rule id），由此建立
「报告中的一条错误 → 具体规则 → 规范条款 → 出处章节」的完整追溯链。
"""

from __future__ import annotations

from ..rules.contracts import RuleSet


def enabled_rule_ids(rules: RuleSet) -> set[str]:
    return {check.id for check in rules.checks if check.enabled}


def summarize_rule_source(rules: RuleSet) -> dict:
    """返回规范来源摘要；无 source 时 `available=False`，不伪造依据。"""
    source = rules.source
    if source is None:
        return {
            "available": False,
            "title": rules.name,
            "document": None,
            "organization": None,
            "scope": None,
            "clauses": [],
            "notes": [],
            "automated_clause_count": 0,
            "manual_clause_count": 0,
            "check_count": len(enabled_rule_ids(rules)),
        }

    enabled = enabled_rule_ids(rules)
    clauses = [
        {
            "id": clause.id,
            "title": clause.title,
            "chapter": clause.chapter,
            "text": clause.text,
            "rules": list(clause.rules),
            "automated": clause.automated,
            "rule_count": sum(1 for rule_id in clause.rules if rule_id in enabled),
        }
        for clause in source.clauses
    ]
    return {
        "available": True,
        "title": source.title,
        "document": source.document,
        "organization": source.organization,
        "scope": source.scope,
        "clauses": clauses,
        "notes": list(source.notes),
        "automated_clause_count": sum(1 for clause in clauses if clause["automated"]),
        "manual_clause_count": sum(1 for clause in clauses if not clause["automated"]),
        "check_count": len(enabled),
    }


def clauses_by_rule_id(rules: RuleSet) -> dict[str, dict]:
    """规则 id → 所属条款，用于给每条错误标注规范出处。"""
    mapping: dict[str, dict] = {}
    for clause in summarize_rule_source(rules)["clauses"]:
        for rule_id in clause["rules"]:
            mapping.setdefault(rule_id, clause)
    return mapping


def unmapped_rule_ids(rules: RuleSet) -> list[str]:
    """返回没有归入任何条款的启用规则，防止新增检查项后摘要失真。"""
    mapped = clauses_by_rule_id(rules)
    return sorted(rule_id for rule_id in enabled_rule_ids(rules) if rule_id not in mapped)


def rule_basis_text(rules: RuleSet) -> str:
    """一句话版的检测依据，供报告正文与接口文案使用。"""
    summary = summarize_rule_source(rules)
    if not summary["available"]:
        return f"规则集「{rules.name}」未登记来源规范，请联系管理员补充 rules.source。"
    basis = f"《{summary['title']}》（{summary['document']}）"
    automated = summary["automated_clause_count"]
    return (
        f"本报告依据{basis}的 {len(summary['clauses'])} 条条款执行检查，"
        f"其中 {automated} 条已由 {summary['check_count']} 项规则自动校对，其余条款需人工核对。"
    )
