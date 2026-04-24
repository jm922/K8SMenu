#!/usr/bin/env python3
"""
System tools menu wrapper for K8S Manager.

Purpose:
- Provide a stable top-level menu entry for option 7 in main.py
- Dynamically load existing tool modules in /tools
- Call their menu/entry functions if available

All comments and print messages are in English.
"""

import importlib.util
import inspect
import os

from utils.color import cprint, Color


TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))


TOOL_MODULES = {
    "1": {
        "label": "System Upgrade",
        "file": "upgrade.py",
        "functions": [
            "upgrade_menu",
            "system_upgrade_menu",
            "main_menu",
            "menu",
        ],
        "keywords": ["menu", "main", "start", "run", "upgrade"],
    },
    "2": {
        "label": "YAML Management",
        "file": "yaml_management.py",
        "functions": [
            "yaml_management_menu",
            "yaml_menu",
            "main_menu",
            "menu",
        ],
        "keywords": ["menu", "main", "start", "run", "yaml"],
    },
    "3": {
        "label": "GitHub Upload",
        "file": "github_upload.py",
        "functions": [
            "github_upload_menu",
            "upload_menu",
            "github_menu",
            "main_menu",
            "menu",
        ],
        "keywords": ["menu", "main", "start", "run", "github", "upload"],
    },
}


BLOCKED_NAME_PREFIXES = (
    "cleanup_",
    "load_",
    "save_",
    "check_",
    "validate_",
    "print_",
    "get_",
    "set_",
    "build_",
    "create_",
    "delete_",
    "remove_",
    "update_",
)


def _pause():
    input("\nPress Enter to continue...")


def _import_module_from_path(module_name, file_path):
    """
    Import a Python module directly from file path.
    """
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot create import spec for {file_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _has_zero_required_args(func):
    """
    Return True if function can be called with no required positional arguments.
    """
    try:
        sig = inspect.signature(func)
    except (TypeError, ValueError):
        return False

    for param in sig.parameters.values():
        if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            continue

        if param.default is inspect.Parameter.empty and param.kind in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        ):
            return False

    return True


def _is_reasonable_entry_name(name):
    """
    Reject helper-style function names that should not be treated as menu entries.
    """
    lowered = name.lower()

    for prefix in BLOCKED_NAME_PREFIXES:
        if lowered.startswith(prefix):
            return False

    return True


def _list_public_callables(module):
    """
    Return a sorted list of public callable names from a module.
    """
    results = []
    for name in dir(module):
        if name.startswith("_"):
            continue
        value = getattr(module, name, None)
        if callable(value):
            results.append(name)
    return sorted(results)


def _list_zero_arg_public_callables(module):
    """
    Return sorted public callable names that can be called with zero required args.
    """
    results = []
    for name in _list_public_callables(module):
        value = getattr(module, name, None)
        if callable(value) and _has_zero_required_args(value):
            results.append(name)
    return sorted(results)


def _find_callable_by_name(module, function_names):
    """
    Return the first callable found from function_names,
    but only if it is safe to call without required args.
    """
    for func_name in function_names:
        func = getattr(module, func_name, None)
        if callable(func) and _has_zero_required_args(func):
            return func, func_name
    return None, None


def _find_callable_by_keywords(module, keywords):
    """
    Try to find a likely entry function by keywords.
    Priority:
    1. names containing 'menu'
    2. names containing 'main'
    3. names containing any configured keyword

    Only zero-required-arg functions are allowed.
    """
    candidates = _list_zero_arg_public_callables(module)
    if not candidates:
        return None, None, candidates

    filtered = [name for name in candidates if _is_reasonable_entry_name(name)]
    if filtered:
        candidates = filtered

    # Strong preference for menu-like names
    for name in candidates:
        lowered = name.lower()
        if "menu" in lowered:
            func = getattr(module, name, None)
            if callable(func):
                return func, name, candidates

    for name in candidates:
        lowered = name.lower()
        if "main" in lowered:
            func = getattr(module, name, None)
            if callable(func):
                return func, name, candidates

    for name in candidates:
        lowered = name.lower()
        for keyword in keywords:
            if keyword in lowered:
                func = getattr(module, name, None)
                if callable(func):
                    return func, name, candidates

    return None, None, candidates


def _run_tool(tool_config):
    """
    Load the selected tool module and run the first matching entry function.
    """
    file_name = tool_config["file"]
    file_path = os.path.join(TOOLS_DIR, file_name)

    if not os.path.exists(file_path):
        cprint(Color.RED, f"Tool file not found: {file_name}")
        _pause()
        return

    module_name = f"_dynamic_tool_{os.path.splitext(file_name)[0]}"

    try:
        module = _import_module_from_path(module_name, file_path)
    except Exception as e:
        cprint(Color.RED, f"Failed to import tool file: {file_name}")
        print(f"Reason: {e}")
        _pause()
        return

    # Step 1: exact function name match
    func, func_name = _find_callable_by_name(module, tool_config["functions"])

    # Step 2: keyword-based fallback using safe zero-arg functions only
    candidate_callables = []
    if not func:
        func, func_name, candidate_callables = _find_callable_by_keywords(
            module,
            tool_config.get("keywords", [])
        )

    if not func:
        cprint(Color.RED, f"No safe menu entry function found in: {file_name}")
        print("Checked exact function names:")
        for name in tool_config["functions"]:
            print(f"- {name}")

        if not candidate_callables:
            candidate_callables = _list_zero_arg_public_callables(module)

        print("\nZero-argument public callable functions found in module:")
        if candidate_callables:
            for name in candidate_callables:
                print(f"- {name}")
        else:
            print("- None")

        print("\nNote:")
        print("- The wrapper only accepts functions with zero required arguments.")
        print("- Helper functions such as cleanup_* are intentionally ignored.")
        _pause()
        return

    print(f"\nResolved entry function: {func_name}")
    print(f"Source file: {file_name}")

    try:
        func()
    except KeyboardInterrupt:
        print()
        cprint(Color.YELLOW, "Operation cancelled by user.")
        _pause()
    except Exception as e:
        cprint(Color.RED, f"Unexpected error while running {tool_config['label']}: {e}")
        print(f"Resolved file: {file_name}")
        print(f"Resolved function: {func_name}")
        _pause()


def system_tools_menu():
    """
    Top-level system tools menu for option 7 in main.py.
    """
    while True:
        print("\n--- K8S Manager System Tools ---")
        print("1. System Upgrade (program update)")
        print("2. YAML Management (YAML utilities)")
        print("3. GitHub Upload (repository upload)")
        print("4. Back (return)")
        choice = input("Choose (1-4): ").strip()

        if choice == "1":
            _run_tool(TOOL_MODULES["1"])
        elif choice == "2":
            _run_tool(TOOL_MODULES["2"])
        elif choice == "3":
            _run_tool(TOOL_MODULES["3"])
        elif choice == "4":
            break
        else:
            cprint(Color.RED, "Invalid option.")
