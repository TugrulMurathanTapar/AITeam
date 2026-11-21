"""
Code Analysis Skill for Multi-AI Orchestrator.

Provides static code inspection, AST parsing, linting, line counting,
and structure analysis for Python and multiple programming languages.
"""

from __future__ import annotations

import ast
import asyncio
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.security_guard import SecurityGuard
from core.skill_manager import BaseSkill

try:
    import aiofiles  # type: ignore

    HAS_AIOFILES = True
except ImportError:
    HAS_AIOFILES = False


class CodeAnalysisSkill(BaseSkill):
    """
    Skill for analyzing source code files.
    
    Inspects syntax errors, line statistics, imports, class hierarchies,
    and function definitions using Python AST and language parsers.
    """

    name: str = "code_analysis"
    description: str = "Analyze code files for structure, issues, and patterns"
    required_permissions: list[str] = ["fs_read"]

    _EXT_TO_LANG = {
        ".py": "python",
        ".js": "javascript",
        ".mjs": "javascript",
        ".cjs": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".jsx": "javascript",
        ".json": "json",
        ".sh": "bash",
        ".bash": "bash",
        ".c": "c",
        ".h": "c",
        ".cpp": "cpp",
        ".hpp": "cpp",
        ".rs": "rust",
        ".go": "go",
        ".java": "java",
        ".rb": "ruby",
        ".php": "php",
        ".html": "html",
        ".css": "css",
        ".sql": "sql",
        ".yaml": "yaml",
        ".yml": "yaml",
    }

    def __init__(self, security_guard: Optional[SecurityGuard] = None) -> None:
        """
        Initialize CodeAnalysisSkill with reference to SecurityGuard.

        Args:
            security_guard: Optional SecurityGuard instance. If None, uses singleton.
        """
        self._security = security_guard if security_guard is not None else SecurityGuard()

    @property
    def parameters_schema(self) -> dict[str, Any]:
        """Tool parameter schema for code_analysis skill."""
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["analyze", "lint", "count_lines", "find_functions"],
                    "description": "Analysis action to perform",
                },
                "path": {
                    "type": "string",
                    "description": "Path to the code file to analyze",
                },
                "language": {
                    "type": "string",
                    "description": "Optional programming language identifier (e.g. 'python')",
                },
            },
            "required": ["action", "path"],
        }

    def _detect_language(self, path: Path, explicit_lang: Optional[str]) -> str:
        """Determine language based on explicit parameter or file suffix."""
        if explicit_lang and explicit_lang.strip():
            return explicit_lang.strip().lower()
        return self._EXT_TO_LANG.get(path.suffix.lower(), "text")

    async def _read_file_content(self, file_path: Path) -> str:
        """Asynchronously read file content."""
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        if not file_path.is_file():
            raise IsADirectoryError(f"Target path is a directory, not a file: {file_path}")

        if HAS_AIOFILES:
            async with aiofiles.open(file_path, mode="r", encoding="utf-8", errors="replace") as f:
                return await f.read()

        def _sync_read() -> str:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                return f.read()

        return await asyncio.to_thread(_sync_read)

    def _count_lines(self, content: str, language: str) -> dict[str, int]:
        """
        Calculate total, blank, comment, and code line counts.

        Args:
            content: Source code text.
            language: Programming language identifier.

        Returns:
            dict[str, int]: Counts of total, blank, comment, and code lines.
        """
        lines = content.splitlines()
        total_lines = len(lines)
        blank_lines = 0
        comment_lines = 0

        # Language specific comment patterns
        hash_comment = language in ("python", "bash", "ruby", "yaml")
        c_style_comment = language in (
            "javascript",
            "typescript",
            "c",
            "cpp",
            "rust",
            "go",
            "java",
            "php",
        )
        dash_comment = language in ("sql", "lua", "haskell")

        in_multiline_block = False

        for line in lines:
            stripped = line.strip()
            if not stripped:
                blank_lines += 1
                continue

            if in_multiline_block:
                comment_lines += 1
                if "*/" in stripped or (hash_comment and (stripped.endswith('"""') or stripped.endswith("'''"))):
                    in_multiline_block = False
                continue

            # Start of block comment
            if c_style_comment and stripped.startswith("/*"):
                comment_lines += 1
                if not stripped.endswith("*/") or stripped == "/*":
                    in_multiline_block = True
                continue

            # Triple quote multiline docstring/comment in python
            if hash_comment and (stripped.startswith('"""') or stripped.startswith("'''")):
                quote_symbol = stripped[:3]
                comment_lines += 1
                if stripped.count(quote_symbol) < 2:
                    in_multiline_block = True
                continue

            # Single line comment checks
            if hash_comment and stripped.startswith("#"):
                comment_lines += 1
            elif c_style_comment and stripped.startswith("//"):
                comment_lines += 1
            elif dash_comment and stripped.startswith("--"):
                comment_lines += 1

        code_lines = max(0, total_lines - blank_lines - comment_lines)
        return {
            "total_lines": total_lines,
            "code_lines": code_lines,
            "blank_lines": blank_lines,
            "comment_lines": comment_lines,
        }

    def _lint_python(self, content: str, path_str: str) -> dict[str, Any]:
        """Perform syntax and semantic structure check for Python code using ast."""
        errors: list[dict[str, Any]] = []
        try:
            tree = ast.parse(content, filename=path_str)
            # Check for duplicate function definitions in the same scope
            seen_defs: set[str] = set()
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.name in seen_defs:
                        errors.append({
                            "line": node.lineno,
                            "column": node.col_offset,
                            "message": f"Duplicate function definition '{node.name}' in top-level scope",
                            "severity": "warning",
                        })
                    seen_defs.add(node.name)
            return {"valid": len(errors) == 0, "errors": errors}
        except SyntaxError as err:
            return {
                "valid": False,
                "errors": [
                    {
                        "line": err.lineno or 1,
                        "column": err.offset or 0,
                        "message": str(err.msg),
                        "text": err.text.strip() if err.text else "",
                        "severity": "error",
                    }
                ],
            }

    def _lint_json(self, content: str) -> dict[str, Any]:
        """Check JSON format validity."""
        try:
            json.loads(content)
            return {"valid": True, "errors": []}
        except json.JSONDecodeError as err:
            return {
                "valid": False,
                "errors": [
                    {
                        "line": err.lineno,
                        "column": err.colno,
                        "message": err.msg,
                        "severity": "error",
                    }
                ],
            }

    def _lint_delimiters(self, content: str) -> dict[str, Any]:
        """Fallback syntax check: validates balanced brackets and delimiters."""
        pairs = {")": "(", "}": "{", "]": "["}
        stack: list[tuple[str, int, int]] = []
        errors: list[dict[str, Any]] = []

        lines = content.splitlines()
        for lineno, line in enumerate(lines, start=1):
            for colno, char in enumerate(line, start=1):
                if char in pairs.values():
                    stack.append((char, lineno, colno))
                elif char in pairs:
                    expected = pairs[char]
                    if not stack or stack[-1][0] != expected:
                        errors.append({
                            "line": lineno,
                            "column": colno,
                            "message": f"Unmatched closing delimiter '{char}'",
                            "severity": "error",
                        })
                    else:
                        stack.pop()

        for open_char, lineno, colno in stack:
            errors.append({
                "line": lineno,
                "column": colno,
                "message": f"Unclosed delimiter '{open_char}'",
                "severity": "error",
            })

        return {"valid": len(errors) == 0, "errors": errors}

    def _find_functions_python(self, content: str) -> list[dict[str, Any]]:
        """Extract all function definitions from Python AST."""
        functions: list[dict[str, Any]] = []
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return functions

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                args_list = [a.arg for a in node.args.args]
                docstring = ast.get_docstring(node)
                end_lineno = getattr(node, "end_lineno", node.lineno)

                # Determine if inside class
                parent_class = None
                for parent in ast.walk(tree):
                    if isinstance(parent, ast.ClassDef):
                        if any(item is node for item in parent.body):
                            parent_class = parent.name
                            break

                functions.append({
                    "name": node.name,
                    "line": node.lineno,
                    "end_line": end_lineno,
                    "is_async": isinstance(node, ast.AsyncFunctionDef),
                    "is_method": parent_class is not None,
                    "parent_class": parent_class,
                    "args": args_list,
                    "docstring": docstring,
                })

        return sorted(functions, key=lambda f: f["line"])

    def _find_functions_generic(self, content: str) -> list[dict[str, Any]]:
        """Regex-based function extraction for JavaScript, TypeScript, and C-like languages."""
        functions: list[dict[str, Any]] = []
        lines = content.splitlines()

        # Matches: function name(args) OR const name = (args) => OR async name(args)
        func_regexes = [
            re.compile(r"(?:export\s+)?(?:async\s+)?function\s+([a-zA-Z0-9_$]+)\s*\(([^)]*)\)"),
            re.compile(r"(?:export\s+)?(?:const|let|var)\s+([a-zA-Z0-9_$]+)\s*=\s*(?:async\s*)?\(([^)]*)\)\s*=>"),
            re.compile(r"^\s*(?:public|private|protected|async|static|\s)*([a-zA-Z0-9_$]+)\s*\(([^)]*)\)\s*\{"),
        ]

        for lineno, line in enumerate(lines, start=1):
            stripped = line.strip()
            for pattern in func_regexes:
                match = pattern.search(stripped)
                if match:
                    func_name = match.group(1)
                    if func_name in ("if", "for", "while", "switch", "catch"):
                        continue
                    raw_args = match.group(2) if len(match.groups()) > 1 else ""
                    args = [a.strip() for a in raw_args.split(",") if a.strip()]
                    functions.append({
                        "name": func_name,
                        "line": lineno,
                        "end_line": lineno,
                        "is_async": "async" in stripped,
                        "is_method": False,
                        "parent_class": None,
                        "args": args,
                        "docstring": None,
                    })
                    break

        return functions

    def _analyze_python(self, content: str, path_str: str) -> dict[str, Any]:
        """Perform complete structural analysis of Python file."""
        stats = self._count_lines(content, "python")
        imports: list[dict[str, Any]] = []
        classes: list[dict[str, Any]] = []
        functions: list[dict[str, Any]] = []

        try:
            tree = ast.parse(content, filename=path_str)
        except SyntaxError:
            return {
                "stats": stats,
                "imports": imports,
                "classes": classes,
                "functions": functions,
                "error": "Failed to parse AST due to syntax error.",
            }

        # Analyze imports
        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append({
                        "type": "import",
                        "module": alias.name,
                        "alias": alias.asname,
                        "line": node.lineno,
                    })
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    imports.append({
                        "type": "from_import",
                        "module": module,
                        "name": alias.name,
                        "alias": alias.asname,
                        "line": node.lineno,
                    })

        # Analyze classes
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                methods = [
                    m.name for m in node.body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
                ]
                bases = []
                for base in node.bases:
                    if isinstance(base, ast.Name):
                        bases.append(base.id)
                    elif isinstance(base, ast.Attribute):
                        bases.append(f"{getattr(base.value, 'id', '')}.{base.attr}")

                classes.append({
                    "name": node.name,
                    "line": node.lineno,
                    "end_line": getattr(node, "end_lineno", node.lineno),
                    "bases": bases,
                    "methods": methods,
                    "docstring": ast.get_docstring(node),
                })

        # Analyze standalone functions
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions.append({
                    "name": node.name,
                    "line": node.lineno,
                    "end_line": getattr(node, "end_lineno", node.lineno),
                    "is_async": isinstance(node, ast.AsyncFunctionDef),
                    "args": [a.arg for a in node.args.args],
                    "docstring": ast.get_docstring(node),
                })

        return {
            "stats": stats,
            "imports": imports,
            "classes": classes,
            "functions": functions,
            "summary": {
                "classes_count": len(classes),
                "standalone_functions_count": len(functions),
                "imports_count": len(imports),
                "code_lines": stats["code_lines"],
            },
        }

    def _analyze_generic(self, content: str, language: str) -> dict[str, Any]:
        """Perform generic regex analysis for non-Python source files."""
        stats = self._count_lines(content, language)
        functions = self._find_functions_generic(content)
        imports: list[dict[str, Any]] = []
        classes: list[dict[str, Any]] = []

        lines = content.splitlines()
        import_pattern = re.compile(r'^\s*(?:import\s+.*|const\s+.*\s*=\s*require\(.*?\);?)')
        class_pattern = re.compile(r'^\s*(?:export\s+)?class\s+([a-zA-Z0-9_$]+)(?:\s+extends\s+([a-zA-Z0-9_$]+))?')

        for lineno, line in enumerate(lines, start=1):
            if import_pattern.match(line):
                imports.append({"statement": line.strip(), "line": lineno})
            class_match = class_pattern.search(line)
            if class_match:
                classes.append({
                    "name": class_match.group(1),
                    "line": lineno,
                    "extends": class_match.group(2) if len(class_match.groups()) > 1 else None,
                })

        return {
            "stats": stats,
            "imports": imports,
            "classes": classes,
            "functions": functions,
            "summary": {
                "classes_count": len(classes),
                "functions_count": len(functions),
                "imports_count": len(imports),
                "code_lines": stats["code_lines"],
            },
        }

    async def execute(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        Execute code analysis action.

        Args:
            params: Dictionary containing:
                - 'action': 'analyze', 'lint', 'count_lines', 'find_functions'
                - 'path': File path to analyze
                - 'language': Optional language name

        Returns:
            dict[str, Any]: Structured code analysis result.
        """
        action = params.get("action")
        raw_path = params.get("path")
        explicit_lang = params.get("language")

        if not action or not isinstance(action, str):
            raise ValueError("Parameter 'action' is required.")
        if not raw_path or not isinstance(raw_path, str):
            raise ValueError("Parameter 'path' is required.")

        action = action.strip().lower()
        file_path = Path(raw_path)

        # Security permission check
        if not self._security.is_path_allowed(file_path):
            raise PermissionError(
                f"Permission denied: path '{raw_path}' is outside allowed paths: "
                f"{self._security.policy.allowed_paths}"
            )

        allowed, reason = self._security.check_permission("fs_read", target_path=file_path)
        if not allowed:
            raise PermissionError(reason)

        content = await self._read_file_content(file_path)
        language = self._detect_language(file_path, explicit_lang)

        if action == "count_lines":
            counts = self._count_lines(content, language)
            return {
                "action": "count_lines",
                "path": str(file_path),
                "language": language,
                **counts,
                "file_size_bytes": len(content.encode("utf-8")),
            }

        elif action == "lint":
            if language == "python":
                lint_res = self._lint_python(content, str(file_path))
            elif language == "json":
                lint_res = self._lint_json(content)
            else:
                lint_res = self._lint_delimiters(content)

            return {
                "action": "lint",
                "path": str(file_path),
                "language": language,
                "valid": lint_res["valid"],
                "errors": lint_res["errors"],
            }

        elif action == "find_functions":
            if language == "python":
                funcs = self._find_functions_python(content)
            else:
                funcs = self._find_functions_generic(content)

            return {
                "action": "find_functions",
                "path": str(file_path),
                "language": language,
                "count": len(funcs),
                "functions": funcs,
            }

        elif action == "analyze":
            if language == "python":
                analysis = self._analyze_python(content, str(file_path))
            else:
                analysis = self._analyze_generic(content, language)

            return {
                "action": "analyze",
                "path": str(file_path),
                "language": language,
                **analysis,
            }

        else:
            raise ValueError(
                f"Unknown action '{action}'. "
                "Supported actions: 'analyze', 'lint', 'count_lines', 'find_functions'."
            )
