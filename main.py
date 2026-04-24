#!/usr/bin/env python3
"""
Main entry point for Kubernetes Resource Manager.

Design:
- Keep startup pre-check
- Use explicit menu routing
- Do not dynamically scan directories or guess menu functions
"""

from utils.color import cprint, Color
from utils.precheck import run_startup_precheck

try:
    from version import VERSION
except Exception:
    VERSION = "Unknown"

# Explicit menu imports
from resources.pod import pod_menu
from resources.service import service_menu
from resources.deployment import deployment_menu
from maintenance.cluster import cluster_maintenance
from tools.system_tools import system_tools_menu


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


def _feature_in_development(feature_name):
    print(f"\n--- {feature_name} ---")
    cprint(Color.YELLOW, "Feature in development, coming soon.")
    _pause()


def _run_menu_handler(choice):
    """
    Explicit menu routing.
    """
    try:
        if choice == "1":
            pod_menu()
        elif choice == "2":
            service_menu()
        elif choice == "3":
            _feature_in_development("Ingress Management")
        elif choice == "4":
            deployment_menu()
        elif choice == "5":
            _feature_in_development("DaemonSet Management")
        elif choice == "6":
            cluster_maintenance()
        elif choice == "7":
            system_tools_menu()
        else:
            cprint(Color.RED, "Invalid option.")
    except KeyboardInterrupt:
        print()
        cprint(Color.YELLOW, "Operation cancelled by user.")
        _pause()
    except Exception as e:
        cprint(Color.RED, f"Unexpected error while running menu option {choice}: {e}")
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
