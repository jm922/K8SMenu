#!/usr/bin/env python3
"""
Cluster maintenance functions
"""

import subprocess
from utils.color import cprint, Color
from utils.lang import t
from maintenance.version_history import show_version_history

def show_cluster_info():
    print("\n" + t("cluster_info_title"))
    result = subprocess.run(['kubectl', 'cluster-info'], capture_output=True, text=True)
    if result.returncode == 0:
        print(result.stdout)
    else:
        cprint(Color.RED, t("fail") + ": " + result.stderr)
    print("\n--- Kubernetes Version ---")
    result = subprocess.run(['kubectl', 'version'], capture_output=True, text=True)
    if result.returncode == 0:
        print(result.stdout)
    else:
        cprint(Color.RED, t("fail") + ": " + result.stderr)
    input(t("press_enter"))

def show_nodes_info():
    print("\n" + t("nodes_info_title"))
    result = subprocess.run(['kubectl', 'get', 'nodes', '-o', 'wide'], capture_output=True, text=True)
    if result.returncode == 0:
        print(result.stdout)
    else:
        cprint(Color.RED, t("fail") + " " + t("nodes_info_fail") + ": " + result.stderr)
    input(t("press_enter"))

def cluster_maintenance():
    while True:
        print("\n" + t("cluster_menu_title"))
        print(t("cluster_menu_1"))
        print(t("cluster_menu_2"))
        print(t("cluster_menu_3"))
        print(t("cluster_menu_4"))
        choice = input(t("cluster_menu_prompt")).strip()
        if choice == '1':
            show_cluster_info()
        elif choice == '2':
            show_nodes_info()
        elif choice == '3':
            show_version_history()
        elif choice == '4':
            break
        else:
            cprint(Color.RED, t("invalid_option"))
