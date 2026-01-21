#!/usr/bin/env python3
"""Reachability analysis: Find code reachable from entry points.

This script traces all Python files reachable from known entry points
(CLI, demo scripts) to identify:
1. In-scope code (reachable from entry points)
2. Out-of-scope code (unreachable, candidates for removal)

Usage:
    python scripts/analyze_reachability.py

Output:
    - Prints reachability report to stdout
    - Creates reachability_report.txt
    - Creates unreachable_files.txt for review
"""

import ast
from pathlib import Path
import sys

# ANSI color codes
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"


def resolve_relative_import(
    module: str, current_file: Path, search_roots: list[Path]
) -> Path | None:
    """Resolve relative import to absolute file path.

    Args:
        module: Relative module name (e.g., '.base', '..context')
        current_file: Path to file containing the import
        search_roots: List of directories to search in (unused, kept for API compatibility)

    Returns:
        Path to file if found, None otherwise

    Example:
        >>> resolve_relative_import('.base', Path('packages/blinkb0t/core/domains/sequencing/moving_heads/transitions/handlers/crossfade.py'), [])
        Path('packages/blinkb0t/core/domains/sequencing/moving_heads/transitions/handlers/base.py')
    """
    if not module.startswith("."):
        return None

    # Count leading dots to determine relative level
    # '.' = current package, '..' = parent package, '...' = grandparent, etc.
    dots = len(module) - len(module.lstrip("."))
    module_name = module.lstrip(".")

    # Get current file's directory
    current_dir = current_file.parent

    # Navigate up directories based on dot count
    # dots=1 ('.') -> stay in current_dir
    # dots=2 ('..') -> go up 1 level
    # dots=3 ('...') -> go up 2 levels
    target_dir = current_dir
    for _ in range(dots - 1):
        target_dir = target_dir.parent

    # Build target path
    if module_name:
        # Module name specified: e.g., '..context' -> parent/context
        # Split by dots to handle nested imports like '..handlers.base'
        parts = module_name.split(".")

        # Navigate through intermediate directories
        for part in parts[:-1]:
            target_dir = target_dir / part

        # For the last part, try both file and directory
        last_part = parts[-1]

        # Try .py file first
        py_file = target_dir / f"{last_part}.py"
        if py_file.exists():
            return py_file

        # Try __init__.py in directory
        init_file = (target_dir / last_part) / "__init__.py"
        if init_file.exists():
            return init_file
    else:
        # No module name: e.g., '..' -> parent's __init__.py
        init_file = target_dir / "__init__.py"
        if init_file.exists():
            return init_file

    return None


def find_imports(file_path: Path, search_roots: list[Path]) -> set[Path]:
    """Extract all imports from Python file and resolve to file paths.

    Args:
        file_path: Path to Python file
        search_roots: List of directories to search for modules

    Returns:
        Set of file paths for imported modules

    Example:
        >>> find_imports(Path("cli/main.py"), [Path('packages')])
        {Path('packages/blinkb0t/core/session.py'), ...}
    """
    try:
        with file_path.open(encoding="utf-8") as f:
            content = f.read()
            tree = ast.parse(content, filename=str(file_path))
    except (SyntaxError, UnicodeDecodeError) as e:
        print(f"{YELLOW}Warning: Could not parse {file_path}: {e}{RESET}", file=sys.stderr)
        return set()

    imported_files = set()

    for node in ast.walk(tree):
        # Check for TYPE_CHECKING import guard
        if (
            isinstance(node, ast.If)
            and isinstance(node.test, ast.Name)
            and node.test.id == "TYPE_CHECKING"
        ):
            # Still process imports in TYPE_CHECKING blocks (they're still reachable)
            continue

        if isinstance(node, ast.Import):
            for alias in node.names:
                module_name = alias.name
                # Only process blinkb0t imports
                if module_name.startswith("blinkb0t"):
                    file_path_resolved = module_to_file(module_name, search_roots)
                    if file_path_resolved:
                        imported_files.add(file_path_resolved)

        elif isinstance(node, ast.ImportFrom) and node.module:
            module_name = node.module

            # Handle relative imports
            if module_name.startswith("."):
                resolved = resolve_relative_import(module_name, file_path, search_roots)
                if resolved:
                    imported_files.add(resolved)
            # Handle absolute blinkb0t imports
            elif module_name.startswith("blinkb0t"):
                # Try the module itself
                file_path_resolved = module_to_file(module_name, search_roots)
                if file_path_resolved:
                    imported_files.add(file_path_resolved)

                # Also add parent modules (e.g., blinkb0t.core from blinkb0t.core.session)
                parts = module_name.split(".")
                for i in range(len(parts)):
                    parent_module = ".".join(parts[: i + 1])
                    parent_file = module_to_file(parent_module, search_roots)
                    if parent_file:
                        imported_files.add(parent_file)

    return imported_files


def module_to_file(module_name: str, search_roots: list[Path]) -> Path | None:
    """Convert module name to file path.

    Args:
        module_name: Module name like 'blinkb0t.core.session'
        search_roots: List of directories to search in

    Returns:
        Path to file if found, None otherwise

    Example:
        >>> module_to_file('blinkb0t.core.session', [Path('packages')])
        Path('packages/blinkb0t/core/session.py')
    """
    # Convert module path to file path
    relative_path = module_name.replace(".", "/")

    # Try direct .py file
    for root in search_roots:
        file_path = root / f"{relative_path}.py"
        if file_path.exists():
            return file_path

        # Try __init__.py in directory
        init_path = root / relative_path / "__init__.py"
        if init_path.exists():
            return init_path

    return None


def build_reachable_set(entry_points: list[Path], search_roots: list[Path]) -> set[Path]:
    """Build set of files reachable from entry points.

    Uses breadth-first search to trace all imports from entry points.

    Args:
        entry_points: Starting files (e.g., cli/main.py)
        search_roots: Directories to search for modules

    Returns:
        Set of all reachable Python files
    """
    visited = set()
    to_visit = list(entry_points)

    print(f"{BLUE}Tracing dependencies from entry points...{RESET}")

    iteration = 0
    while to_visit:
        iteration += 1
        current = to_visit.pop(0)

        if current in visited:
            continue

        if iteration % 50 == 0:
            print(f"  Iteration {iteration}: {len(visited)} files visited, {len(to_visit)} queued")

        visited.add(current)

        # Find imports in current file (now returns file paths directly)
        imported_files = find_imports(current, search_roots)

        # Add imported files to queue
        for imported_file in imported_files:
            if imported_file not in visited and imported_file.exists():
                to_visit.append(imported_file)

    print(f"  {GREEN}Complete: {len(visited)} reachable files{RESET}\n")
    return visited


def find_all_python_files(root: Path) -> set[Path]:
    """Find all Python files in directory tree.

    Args:
        root: Root directory to search

    Returns:
        Set of all .py files (excluding __pycache__)
    """
    return {f for f in root.rglob("*.py") if "__pycache__" not in str(f)}


def categorize_unreachable(unreachable: list[Path], repo_root: Path) -> dict:
    """Categorize unreachable files by pattern.

    Returns:
        Dict mapping category name to list of files
    """
    categories = {
        "legacy": [],
        "backup": [],
        "test_fixtures": [],
        "empty": [],
        "other": [],
    }

    for f in unreachable:
        rel_path = f.relative_to(repo_root)

        if "legacy" in str(f).lower() or "old" in str(f).lower():
            categories["legacy"].append(rel_path)
        elif ".bak" in str(f):
            categories["backup"].append(rel_path)
        elif "test" in str(f) and "fixture" in str(f):
            categories["test_fixtures"].append(rel_path)
        elif f.stat().st_size < 100:  # <100 bytes, likely empty
            categories["empty"].append(rel_path)
        else:
            categories["other"].append(rel_path)

    return categories


def generate_report(
    reachable: set[Path],
    unreachable: list[Path],
    categories: dict,
    repo_root: Path,
) -> str:
    """Generate human-readable report."""
    total_files = len(reachable) + len(unreachable)

    report = []
    report.append("=" * 80)
    report.append("REACHABILITY ANALYSIS REPORT")
    report.append("=" * 80)
    report.append("")

    report.append("SUMMARY")
    report.append("-" * 80)
    report.append(f"Total Python files:     {total_files}")
    report.append(
        f"Reachable (IN SCOPE):   {len(reachable)} ({len(reachable) / total_files * 100:.1f}%)"
    )
    report.append(
        f"Unreachable (OUT):      {len(unreachable)} ({len(unreachable) / total_files * 100:.1f}%)"
    )
    report.append("")

    report.append("UNREACHABLE FILES BY CATEGORY")
    report.append("-" * 80)

    for category, files in categories.items():
        if files:
            report.append(f"\n{category.upper()} ({len(files)} files):")
            for f in sorted(files):
                report.append(f"  - {f}")

    report.append("")
    report.append("=" * 80)
    report.append("RECOMMENDATIONS")
    report.append("=" * 80)
    report.append("")
    report.append("1. IMMEDIATE (Remove Today):")
    report.append("   - All backup files (*.bak)")
    report.append("   - All files in 'legacy' category")
    report.append("   - Empty placeholder files")
    report.append("")
    report.append("2. VERIFY (Manual Review):")
    report.append("   - Files in 'other' category")
    report.append("   - Check for dynamic imports (eval, importlib)")
    report.append("   - Check git history for context")
    report.append("")
    report.append("3. DOCUMENT:")
    report.append("   - Create docs/architecture/in_scope.md")
    report.append("   - List all entry points")
    report.append("   - Document dependency flow")
    report.append("")

    return "\n".join(report)


def main():
    """Main entry point."""
    # Determine repo root
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent

    print(f"{BLUE}Repository root: {repo_root}{RESET}\n")

    # Define entry points - include all demo scripts
    entry_points = [
        repo_root / "packages/blinkb0t/cli/main.py",
        repo_root / "scripts/demo.py",
        repo_root / "scripts/demo_template_render_console.py",
        repo_root / "scripts/demo_sequencev2_console.py",
        repo_root / "scripts/demo_curve_looping_transitions.py",
    ]

    # Filter to only existing entry points
    existing_entry_points = [ep for ep in entry_points if ep.exists()]
    missing_entry_points = [ep for ep in entry_points if not ep.exists()]

    if missing_entry_points:
        print(f"{YELLOW}Warning: Some entry points not found:{RESET}")
        for ep in missing_entry_points:
            print(f"  - {ep.relative_to(repo_root)}")
        print()

    if not existing_entry_points:
        print(f"{RED}Error: No entry points found!{RESET}")
        sys.exit(1)

    print(f"{GREEN}Entry points:{RESET}")
    for ep in existing_entry_points:
        print(f"  - {ep.relative_to(repo_root)}")
    print()

    # Define search roots
    search_roots = [
        repo_root / "packages",
        repo_root / "scripts",
    ]

    # Build reachable set
    reachable = build_reachable_set(existing_entry_points, search_roots)

    # Find all Python files
    all_files = set()
    for root in [repo_root / "packages/blinkb0t/core"]:
        all_files.update(find_all_python_files(root))

    print(f"{BLUE}Total Python files in core: {len(all_files)}{RESET}\n")

    # Find unreachable files
    unreachable = sorted(all_files - reachable)

    # Categorize
    categories = categorize_unreachable(unreachable, repo_root)

    # Generate report
    report = generate_report(reachable, unreachable, categories, repo_root)

    # Print to stdout
    print(report)

    # Save to file
    report_file = repo_root / "reachability_report.txt"
    with report_file.open("w") as f:
        f.write(report)
    print(f"\n{GREEN}Report saved to: {report_file}{RESET}")

    # Save unreachable files list
    unreachable_file = repo_root / "unreachable_files.txt"
    with unreachable_file.open("w") as f:
        for path in unreachable:
            f.write(f"{path.relative_to(repo_root)}\n")
    print(f"{GREEN}Unreachable files list: {unreachable_file}{RESET}")

    # Exit with status code
    if unreachable:
        sys.exit(1)  # Unreachable files found
    else:
        sys.exit(0)  # All files reachable


if __name__ == "__main__":
    main()
