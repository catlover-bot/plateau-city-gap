from __future__ import annotations

import ast
from pathlib import Path


def test_every_pytest_skip_is_classified_and_none_are_unimplemented() -> None:
    reasons: list[str] = []
    for root in (Path("backend"), Path("analysis")):
        for path in root.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                    continue
                if not (
                    isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "pytest"
                    and node.func.attr == "skip"
                ):
                    continue
                assert node.args and isinstance(node.args[0], ast.Constant), path
                reasons.append(str(node.args[0].value))

    assert reasons
    assert all(
        reason.startswith(("EXPECTED_EXTERNAL:", "ENVIRONMENT_SPECIFIC:"))
        for reason in reasons
    )
    assert not any(reason.startswith("UNIMPLEMENTED:") for reason in reasons)
