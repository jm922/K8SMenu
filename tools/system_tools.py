#!/usr/bin/env python3
"""
Top-level system tools menu for K8S Manager.

Design:
- Use explicit routing
- Do not dynamically scan files or guess entry functions
- Support both:
  1. future standard menu wrapper names
  2. current legacy function names
"""

from utils.color import cprint, Color


def _pause():
    input("\nPress Enter to continue...")


# Upgrade entry
try:
    from tools.upgrade import system_upgrade_menu as _system_upgrade_entry
except Exception:
    try:
        from tools.upgrade import program_upgrade as _system_upgrade_entry
    except Exception:
        _system_upgrade_entry = None


# YAML management entry
try:
    from tools.yaml_management import yaml_management_menu as _yaml_management_entry
except Exception:
    try:
        from tools.yaml_management import yaml_file_management as _yaml_management_entry
    except Exception:
        _yaml_management_entry = None


# GitHub upload entry
try:
    from tools.github_upload import github_upload_menu as _github_upload_entry
except Exception:
    try:
        from tools.github_upload import upload_to_github_git as _github_upload_entry
    except Exception:
        _github_upload_entry = None


def _run_tool(tool_name, func):
    """
    Run a tool entry function safely.
    """
    if not callable(func):
        cprint(Color.RED, f"{tool_name} is not available.")
        cprint(Color.YELLOW, "The target module or entry function could not be loaded.")
        _pause()
        return

    try:
        func()
    except KeyboardInterrupt:
        print()
        cprint(Color.YELLOW, "Operation cancelled by user.")
        _pause()
    except Exception as e:
        cprint(Color.RED, f"Unexpected error while running {tool_name}: {e}")
        _pause()


def system_tools_menu():
    """
    Top-level menu for option 7 in main.py.
    """
    while True:
        print("\n--- K8S Manager System Tools ---")
        print("1. System Upgrade (program update)")
        print("2. YAML Management (YAML utilities)")
        print("3. GitHub Upload (repository upload)")
        print("4. Back (return)")
        choice = input("Choose (1-4): ").strip()

        if choice == "1":
            _run_tool("System Upgrade", _system_upgrade_entry)
        elif choice == "2":
            _run_tool("YAML Management", _yaml_management_entry)
        elif choice == "3":
            _run_tool("GitHub Upload", _github_upload_entry)
        elif choice == "4":
            break
        else:
            cprint(Color.RED, "Invalid option.")
