#!/usr/bin/env python3
"""
Main entry point for Kubernetes Resource Manager.
Includes non-blocking startup pre-check before showing the main menu.
"""

import importlib.util
import os
import sys

from utils.color import cprint, Color
from utils.precheck import run_startup_precheck

try:
    from version import VERSION
except Exception:
    VERSION = "Unknown"


BASE_DIR = os.path.dirname(os.path.abspath(__file__))


MENU_CONFIG = {
    "1": {
        "label": "POD",
        "directory": "resources",
        "preferred_files": ["pod.py", "pods.py"],
        "preferred_functions": ["pod_menu", "pods_menu", "menu", "main_menu"],
    },
    "2": {
        "label": "SERVICE",
        "directory": "resources",
        "preferred_files": ["service.py", "services.py"],
        "preferred_functions": ["service_menu", "services_menu", "menu", "main_menu"],
    },
    "3": {
        "label": "INGRESS",
        "directory": "resources",
        "preferred_files": ["ingress.py"],
        "preferred_functions": ["ingress_menu", "menu", "main_menu"],
    },
    "4": {
        "label": "DEPLOYMENT",
        "directory": "resources",
        "preferred_files": ["deployment.py"],
        "preferred_functions": ["deployment_menu", "menu", "main_menu"],
    },
    "5": {
        "label": "DAEMONSET",
        "directory": "resources",
        "preferred_files": ["daemonset.py", "daemon_set.py"],
        "preferred_functions": ["daemonset_menu", "daemon_set_menu", "menu", "main_menu"],
    },
    "6": {
        "label": "K8S CLUSTER MAINTENANCE",
        "directory": "maintenance",
        "preferred_files": ["cluster_maintenance.py", "maintenance.py", "cluster.py"],
        "preferred_functions": [
            "cluster_maintenance_menu",
            "maintenance_menu",
            "menu",
            "main_menu",
        ],
    },
    "7": {
        "label": "K8S MANAGER SYSTEM TOOLS",
        "directory": "tools",
        "preferred_files": ["system_tools.py", "manager_tools.py", "k8s_manager_tools.py"],
        "preferred_functions": [
            "system_tools_menu",
            "tools_menu",
            "manager_tools_menu",
            "k8s_manager_tools_menu",
            "menu",
            "main_menu",
        ],
    },
}


def _pause():
    input("\nPress Enter to continue...")


def _get_version_text():
    version_text = str(VERSION).strip()
    if not version_text:
        return "Unknown"
    if version_text.lower().startswith("v"):
        return version_text
    return f"V{version_text}"


def _print_main_header():
    print("\n========================================")
    print(f"Kubernetes Resource Manager {_get_version_text()}")
    print("========================================")


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


def _try_functions_from_module(module, function_names):
    """
    Return the first callable function found from function_names.
    """
    for func_name in function_names:
        func = getattr(module, func_name, None)
        if callable(func):
            return func, func_name
    return None, None


def _list_python_files(directory_path):
    """
    Return sorted list of .py files in a directory, excluding __init__.py.
    """
    if not os.path.isdir(directory_path):
        return []

    files = []
    for name in os.listdir(directory_path):
        if not name.endswith(".py"):
            continue
        if name == "__init__.py":
            continue
        files.append(name)

    return sorted(files)


def _build_candidate_file_list(directory_path, preferred_files):
    """
    Build candidate file list:
    1. preferred files first
    2. all other .py files in the directory
    """
    existing_files = _list_python_files(directory_path)
    ordered = []

    for name in preferred_files:
        if name in existing_files and name not in ordered:
            ordered.append(name)

    for name in existing_files:
        if name not in ordered:
            ordered.append(name)

    return ordered


def _load_menu_callable(choice):
    """
    Load a menu handler from configured directory and Python files.
    Returns:
        (callable_or_none, resolved_file_or_none, resolved_func_or_none, checked_items)
    """
    config = MENU_CONFIG.get(choice)
    if not config:
        return None, None, None, []

    directory_path = os.path.join(BASE_DIR, config["directory"])
    candidate_files = _build_candidate_file_list(directory_path, config["preferred_files"])
    checked_items = []

    for filename in candidate_files:
        file_path = os.path.join(directory_path, filename)
        module_name = f"_dynamic_{config['directory']}_{os.path.splitext(filename)[0]}"

        try:
            module = _import_module_from_path(module_name, file_path)
            func, func_name = _try_functions_from_module(module, config["preferred_functions"])
            checked_items.append(f"{filename} -> {', '.join(config['preferred_functions'])}")

            if callable(func):
                return func, file_path, func_name, checked_items

        except Exception as e:
            checked_items.append(f"{filename} -> import failed: {e}")

    return None, None, None, checked_items


def _run_menu_handler(choice):
    """
    Resolve and run the selected menu handler safely.
    """
    config = MENU_CONFIG.get(choice)
    if not config:
        cprint(Color.RED, "Invalid option.")
        return

    func, resolved_file, resolved_func, checked_items = _load_menu_callable(choice)

    if not func:
        cprint(Color.RED, f"Menu handler not found for: {config['label']}")
        print("Checked files/functions:")
        for item in checked_items:
            print(f"- {item}")
        _pause()
        return

    try:
        func()
    except KeyboardInterrupt:
        print()
        cprint(Color.YELLOW, "Operation cancelled by user.")
        _pause()
    except Exception as e:
        cprint(Color.RED, f"Unexpected error while running {config['label']}: {e}")
        print(f"Resolved handler file: {resolved_file}")
        print(f"Resolved handler func: {resolved_func}")
        _pause()


def main_menu():
    """
    Main menu loop.
    """
    while True:
        _print_main_header()
        print("1. POD")
        print("2. SERVICE")
        print("3. INGRESS")
        print("4. DEPLOYMENT")
        print("5. DAEMONSET")
        print("6. K8S CLUSTER MAINTENANCE")
        print("7. K8S MANAGER SYSTEM TOOLS")
        print("8. Exit")

        choice = input("Select resource type (1-8): ").strip()

        if choice == "8":
            print("Goodbye!")
            break

        _run_menu_handler(choice)


if __name__ == "__main__":
    run_startup_precheck()
    main_menu()
