"""Verify the requested Python public-function documentation contract without executing application code."""
import ast
from pathlib import Path


def main():
    """Scan public module/class functions and fail if documentation is absent; print only file/function names."""
    root = Path(__file__).resolve().parents[1] / "backend" / "app"
    missing = []
    for file in root.glob("*.py"):
        module = ast.parse(file.read_text(encoding="utf-8"))
        scopes = [module, *[n for n in module.body if isinstance(n, ast.ClassDef)]]
        for scope in scopes:
            for node in scope.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_") and not ast.get_docstring(node):
                    missing.append(f"{file.name}:{node.lineno} {node.name}")
    if missing:
        raise SystemExit("\n".join(missing))
    print("All public Python functions and endpoints have docstrings.")


if __name__ == "__main__":
    main()
