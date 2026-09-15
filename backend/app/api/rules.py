"""规则集目录接口：列出扫描到的规则文件，供前端选择检测依据。"""

from fastapi import APIRouter, HTTPException

from ..rules.registry import (
    RuleSetNotFoundError,
    default_rule_set_id,
    discover_rule_sets,
    resolve_rule_set,
    rules_dir,
)

router = APIRouter(prefix="/rule", tags=["rule"])


@router.get("/list")
def list_rule_sets() -> dict:
    rule_sets = discover_rule_sets()
    return {
        "code": 200,
        "message": "success",
        "data": {
            "rules_dir": str(rules_dir()),
            "default_rule_set_id": default_rule_set_id(),
            "total": len(rule_sets),
            "rule_sets": [info.model_dump() for info in rule_sets],
        },
    }


@router.get("/{rule_set_id}")
def get_rule_set(rule_set_id: str) -> dict:
    try:
        resolved = resolve_rule_set(rule_set_id)
    except RuleSetNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return {
        "code": 200,
        "message": "success",
        "data": {
            "rule_set": resolved.info.model_dump(),
            "checks": [check.model_dump() for check in resolved.rules.checks],
        },
    }
