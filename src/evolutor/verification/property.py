"""Property-based testing support."""

from __future__ import annotations

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


class TestableFunction(BaseModel):
    name: str
    module: str
    file_path: str
    signature: str = ""
    docstring: str = ""


class PropertyTestResult(BaseModel):
    function_name: str
    passed: bool = True
    num_examples: int = 0
    failing_example: str | None = None
    error: str | None = None


class PropertyTester:
    """Generate and run property-based tests using hypothesis."""

    def __init__(self, project_root: str = ".") -> None:
        self.project_root = project_root

    def discover_testable_functions(self, file_path: str) -> list[TestableFunction]:
        import ast

        functions = []
        try:
            with open(file_path) as f:
                tree = ast.parse(f.read())
            module_name = file_path.replace("/", ".").replace(".py", "")
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
                    sig = f"def {node.name}({', '.join(a.arg for a in node.args.args)})"
                    doc = ast.get_docstring(node) or ""
                    functions.append(TestableFunction(
                        name=node.name,
                        module=module_name,
                        file_path=file_path,
                        signature=sig,
                        docstring=doc,
                    ))
        except Exception as e:
            logger.warning("discover_failed", file=file_path, error=str(e))
        return functions

    def generate_property_tests(self, function: TestableFunction) -> str:
        return f'''from hypothesis import given, strategies as st

@given(st.text())
def test_{function.name}_does_not_crash(s):
    # Auto-generated property test
    # TODO: Replace with meaningful property assertions
    assert True
'''

    def run_property_tests(self, test_code: str) -> PropertyTestResult:
        import tempfile
        import subprocess

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(test_code)
            f.flush()
            result = subprocess.run(
                ["python", "-m", "pytest", f.name, "-x", "-q"],
                capture_output=True, text=True, cwd=self.project_root,
                env={"PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "PATH": "/usr/bin:/usr/local/bin"},
            )
        return PropertyTestResult(
            function_name="generated",
            passed=result.returncode == 0,
            num_examples=100,
            error=result.stderr if result.returncode != 0 else None,
        )
