#!/usr/bin/env python3
"""
Main entry point for Kubernetes Resource Manager
"""

import sys
from utils.color import cprint, Color
from utils.lang import t
from utils.helpers import check_kubectl
from version import VERSION, init_version_log
from resources.pod import pod_menu
from resources.deployment import deployment_menu
from tools.yaml_management import yaml_file_management
from tools.upgrade import program_upgrade
from tools.github_upload import upload_to_github_git
from maintenance.cluster import cluster_maintenance

def service_menu():
    print("\n" + t("service_menu_title"))
    cprint(Color.YELLOW, t("service_menu_dev"))
    input(t("press_enter"))

def ingress_menu():
    print("\n" + t("ingress_menu_title"))
    cprint(Color.YELLOW, t("service_menu_dev"))
    input(t("press_enter"))

def daemonset_menu():
    print("\n" + t("daemonset_menu_title"))
    cprint(Color.YELLOW, t("service_menu_dev"))
    input(t("press_enter"))

def manager_system_tools():
    while True:
        print("\n" + t("tools_menu_title"))
        print(t("tools_menu_1"))
        print(t("tools_menu_2"))
        # 原选项3 (PyGithub) 已移除，Git CLI 成为选项3
        print(t("tools_menu_3"))
        print(t("tools_menu_4"))   # 返回主菜单
        choice = input(t("tools_menu_prompt")).strip()
        if choice == '1':
            program_upgrade()
        elif choice == '2':
            yaml_file_management()
        elif choice == '3':
            upload_to_github_git()
        elif choice == '4':
            break
        else:
            cprint(Color.RED, t("invalid_option"))

def main_menu():
    while True:
        print("\n" + "="*40)
        print(t("main_menu_title", version=VERSION))
        print("="*40)
        print(t("main_menu_1"))
        print(t("main_menu_2"))
        print(t("main_menu_3"))
        print(t("main_menu_4"))
        print(t("main_menu_5"))
        print(t("main_menu_6"))
        print(t("main_menu_7"))
        print(t("main_menu_8"))
        choice = input(t("main_menu_prompt")).strip()

        if choice == '1':
            pod_menu()
        elif choice == '2':
            service_menu()
        elif choice == '3':
            ingress_menu()
        elif choice == '4':
            deployment_menu()
        elif choice == '5':
            daemonset_menu()
        elif choice == '6':
            cluster_maintenance()
        elif choice == '7':
            manager_system_tools()
        elif choice == '8':
            cprint(Color.CYAN, t("goodbye"))
            sys.exit(0)
        else:
            cprint(Color.RED, t("invalid_option"))

if __name__ == "__main__":
    check_kubectl()
    init_version_log()
    main_menu()
