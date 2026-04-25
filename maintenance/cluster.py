#!/usr/bin/env python3
"""
Cluster maintenance functions
"""

import subprocess

from utils.color import cprint, Color
from maintenance.version_history import show_version_history
from resources.node import node_menu


def _pause():
    input("\nPress Enter to continue...")


def _print_command(cmd):
    print("\n" + "-" * 72)
    cprint(Color.BOLD + Color.YELLOW, "Executing command")
    cprint(Color.YELLOW, " ".join(cmd))
    print("-" * 72)


def _run_kubectl_text(args):
    """
    Run kubectl command and return:
    - stdout on success
    - stderr on failure
    """
    cmd = ["kubectl"] + args
    _print_command(cmd)

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True
    )

    if result.returncode == 0:
        return result.stdout, None

    return None, (result.stderr or result.stdout).strip()


def show_cluster_info():
    """
    Show cluster info and Kubernetes version.
    """
    print("\n--- Cluster Info ---")

    output, err = _run_kubectl_text(["cluster-info"])
    if err:
        cprint(Color.RED, f"Failed to get cluster info: {err}")
    else:
        print(output)

    print("\n--- Kubernetes Version ---")
    output, err = _run_kubectl_text(["version"])
    if err:
        cprint(Color.RED, f"Failed to get Kubernetes version: {err}")
    else:
        print(output)

    _pause()


def show_nodes_info():
    """
    Show basic node overview with wide output.
    """
    print("\n--- Nodes Overview ---")

    output, err = _run_kubectl_text(["get", "nodes", "-o", "wide"])
    if err:
        cprint(Color.RED, f"Failed to get nodes overview: {err}")
    else:
        print(output)

    _pause()


def cluster_maintenance():
    """
    Cluster maintenance main menu.
    """
    while True:
        print("\n--- K8S Cluster Maintenance ---")
        print("1. Cluster Info (cluster-info / version)")
        print("2. Nodes Overview (kubectl get nodes -o wide)")
        print("3. Node Management")
        print("4. Version History")
        print("5. Back (return)")

        choice = input("Choose (1-5): ").strip()

        if choice == "1":
            show_cluster_info()
        elif choice == "2":
            show_nodes_info()
        elif choice == "3":
            node_menu()
        elif choice == "4":
            show_version_history()
        elif choice == "5":
            break
        else:
            cprint(Color.RED, "Invalid option.")


def cluster_maintenance_menu():
    """
    Standard zero-argument menu entry for main.py.
    """
    cluster_maintenance()
