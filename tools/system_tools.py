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
        "keywords": ["menu", "upgrade", "main", "run", "start"],
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
        "keywords": ["menu", "yaml", "main", "run", "start"],
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
        "keywords": ["menu", "github", "upload", "main", "run", "start"],
    },
}


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


def _find_callable_by_name(module, function_names):
    """
    Return the first callable found from function_names.
    """
    for func_name in function_names:
        func = getattr(module, func_name, None)
        if callable(func):
            return func, func_name
    return None, None


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


def _find_callable_by_keywords(module, keywords):
    """
    Try to find a likely entry function by keywords.
    Priority:
    1. names containing 'menu'
    2. names containing any configured keyword
    """
    public_callables = _list_public_callables(module)
    if not public_callables:
        return None, None, public_callables

    # Strong preference for *menu*
    for name in public_callables:
        if "menu" in name.lower():
            func = getattr(module, name, None)
            if callable(func):
                return func, name, public_callables

    # Then match configured keywords
    for name in public_callables:
        lowered = name.lower()
        for keyword in keywords:
            if keyword in lowered:
                func = getattr(module, name, None)
                if callable(func):
                    return func, name, public_callables

    return None, None, public_callables


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

    # Step 2: keyword-based fallback
    public_callables = []
    if not func:
        func, func_name, public_callables = _find_callable_by_keywords(
            module,
            tool_config.get("keywords", [])
        )

    if not func:
        cprint(Color.RED, f"No menu entry function found in: {file_name}")
        print("Checked exact function names:")
        for name in tool_config["functions"]:
            print(f"- {name}")

        if not public_callables:
            public_callables = _list_public_callables(module)

        print("\nPublic callable functions found in module:")
        if public_callables:
            for name in public_callables:
                print(f"- {name}")
        else:
            print("- None")

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
