#!/usr/bin/env python3
"""
Version management for Kubernetes Resource Manager
"""

import os
import json
from datetime import datetime
from utils.color import cprint, Color

VERSION = "V0.83"

VERSION_CHANGES = {
    "V0.10": {
        "type": "Initial Release",
        "description": "Initial version release",
        "changes": [
            "POD Management: Create, Delete, List, Describe",
            "System Maintenance: Show cluster info, node info",
            "Program Upgrade: Custom file upgrade, auto backup, auto restart"
        ]
    },
    "V0.20": {
        "type": "Feature Enhancement",
        "description": "Pod management enhanced with number selection",
        "changes": [
            "Pod list displays numbers",
            "Delete Pod supports number selection (no need to enter full name)",
            "Describe Pod supports number selection",
            "Improved interactive experience"
        ]
    },
    "V0.30": {
        "type": "Bug Fix",
        "description": "Fix bugs when deleting pod and improve error handling",
        "changes": [
            "Fixed KeyError when confirming pod deletion",
            "Improved input validation for pod number selection",
            "Enhanced error messages for better user experience",
            "Version tracking properly records all changes"
        ]
    },
    "V0.40": {
        "type": "Feature Enhancement",
        "description": "Added YAML editor mode for Pod creation",
        "changes": [
            "New Create Pod submenu with two options",
            "Quick Deploy: Interactive wizard for fast deployment",
            "YAML Editor: Manual YAML editing with vim",
            "Automatic YAML syntax validation",
            "Kubernetes dry-run validation before deployment",
            "Vim installation check and auto-install option"
        ]
    },
    "V0.50": {
        "type": "Feature Enhancement",
        "description": "Enhanced Pod management and added YAML file management",
        "changes": [
            "Improved Pod list display with aligned columns",
            "Batch delete support for multiple Pods",
            "YAML files now preserved after creation for review",
            "New YAML File Management in System Tools",
            "Renamed menu options for better clarity",
            "Exit options in delete mode"
        ]
    },
    "V0.60": {
        "type": "Feature Enhancement",
        "description": "Added complete Deployment management",
        "changes": [
            "Deployment management with Create, Delete, List, Describe",
            "Quick Deploy and YAML Editor modes for Deployment creation",
            "Batch delete support for Deployments",
            "Aligned listing output for Deployments",
            "Number selection for deletion and description"
        ]
    },
    "V0.70": {
        "type": "Feature Enhancement",
        "description": "Enhanced Deployment list with ReplicaSet and Pod names",
        "changes": [
            "Deployment list now shows the newest ReplicaSet name",
            "Deployment list shows Pod names under that ReplicaSet (up to 3 names, with count)",
            "Improved visibility of Deployment-Pod relationship"
        ]
    },
    "V0.71": {
        "type": "Feature Enhancement",
        "description": "Added export Deployment to YAML (screen or file)",
        "changes": [
            "New menu option 'Export Deployment to YAML'",
            "Option to display YAML directly on screen",
            "Option to save YAML to file with automatic naming and overwrite confirmation"
        ]
    },
    "V0.72": {
        "type": "Feature Enhancement",
        "description": "Added GitHub upload using PyGithub",
        "changes": [
            "New menu option 'Upload to GitHub (PyGithub)'",
            "Upload current script file to specified GitHub repository",
            "Automatic PyGithub library installation if missing",
            "Support for overwriting existing files"
        ]
    },
    "V0.73": {
        "type": "Feature Enhancement",
        "description": "Added GitHub upload using Git CLI",
        "changes": [
            "New menu option 'Upload to GitHub (Git CLI)'",
            "Automatic Git installation if missing (requires sudo)",
            "Automatically initialize git repository if needed",
            "Configure remote origin and push script to GitHub",
            "No need for manual token generation"
        ]
    },
    "V0.74": {
        "type": "Bug Fix",
        "description": "Fixed Git identity configuration in Git CLI upload",
        "changes": [
            "Script now checks and prompts for Git user name and email if missing",
            "Prevents 'Author identity unknown' error when committing"
        ]
    },
    "V0.75": {
        "type": "Improvement",
        "description": "Improved Git CLI upload when no changes detected",
        "changes": [
            "Now attempts to push existing commits even if no new changes",
            "Provides clear feedback when file is already up-to-date"
        ]
    },
    "V0.76": {
        "type": "Feature Enhancement",
        "description": "Redesigned program upgrade with rollback and health check",
        "changes": [
            "Upgrade now works with UPGRADE_TMP directory (recursive .py files)",
            "Automatic backup and permission restoration for each file",
            "Post-upgrade health check (tests program startup)",
            "Automatic rollback if health check fails",
            "Detailed logging in LOG/upgrade_*.log"
        ]
    },
    "V0.77": {
        "type": "Removal",
        "description": "Removed PyGithub upload option (use Git CLI instead)",
        "changes": [
            "Removed 'Upload to GitHub (PyGithub)' from System Tools menu",
            "Git CLI upload now handles entire project (adds all files)",
            "Updated menu numbering for System Tools"
        ]
    },
    "V0.78": {
        "type": "Improvement",
        "description": "Enhanced upgrade script with delay and auto-cleanup",
        "changes": [
            "Added 5-second delays between critical steps for better readability",
            "Upgrade now automatically deletes UPGRADE_TMP directory after success (optional)",
            "Improved user experience with clearer progress indicators"
        ]
    },
    "V0.79": {
        "type": "Feature Enhancement",
        "description": "Added Edit Deployment submenu",
        "changes": [
            "New 'Edit Deployment' option in Deployment management",
            "Direct edit using kubectl edit",
            "Edit via external YAML file with kubectl apply"
        ]
    },
    "V0.80": {
        "type": "Feature Enhancement",
        "description": "Improved Deployment list and edit display",
        "changes": [
            "Deployment list now shows container image column",
            "Direct edit now displays detailed deployment info (name, ready, available, image)",
            "Added exit option (q/menu) in Direct Edit to avoid mandatory selection",
            "Better user experience for selecting deployments to edit"
        ]
    },
    "V0.81": {
        "type": "Feature Enhancement",
        "description": "Enhanced Pod and Deployment listings",
        "changes": [
            "Pod list now shows Namespace and Labels columns",
            "Deployment list removed Pods column (now separate option)",
            "New menu option 'Show Pods of Deployment' to list pods under a specific Deployment",
            "Improved readability with truncated long fields"
        ]
    },
    "V0.82": {
        "type": "Improvement",
        "description": "Integrated Show Pods into Deployment list",
        "changes": [
            "After listing Deployments, you can now optionally view Pods of a selected Deployment",
            "Removed separate 'Show Pods of Deployment' menu option for cleaner interface",
            "Pods display includes Namespace and Labels columns"
        ]
    },
    "V0.83": {
        "type": "Bug Fix",
        "description": "Fixed empty Namespace in Pod list",
        "changes": [
            "Now uses --all-namespaces to fetch pods, so Namespace column shows actual pod namespace",
            "Improved Pod list display with correct namespace information",
            "Show Deployment Pods now also correctly shows namespace"
        ]
    }
}

VERSION_LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".k8s_manager_version")

def init_version_log():
    global VERSION_LOG_FILE
    log_dir = os.path.dirname(VERSION_LOG_FILE)
    if not os.access(log_dir, os.W_OK):
        VERSION_LOG_FILE = os.path.expanduser("~/.k8s_manager_version")
        cprint(Color.YELLOW, f"Current directory not writable, version log will be saved to: {VERSION_LOG_FILE}")

    current_changes = VERSION_CHANGES.get(VERSION, {
        "type": "Unknown Change",
        "description": "No detailed description",
        "changes": ["Please update VERSION_CHANGES dictionary"]
    })
    
    if os.path.exists(VERSION_LOG_FILE):
        try:
            with open(VERSION_LOG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            old_version = data.get("current_version", "V0.00")
        except:
            data = {"current_version": VERSION, "history": []}
            old_version = None
    else:
        old_version = None
        data = {"current_version": VERSION, "history": []}

    if old_version is None:
        data["history"].append({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "old_version": "N/A",
            "new_version": VERSION,
            "change_type": current_changes["type"],
            "description": current_changes["description"],
            "changes": current_changes["changes"]
        })
        try:
            with open(VERSION_LOG_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            cprint(Color.GREEN, f"Initialized version log, current version: {VERSION}")
        except Exception as e:
            cprint(Color.RED, f"Unable to write version log: {e}")
    elif old_version != VERSION:
        data["current_version"] = VERSION
        data["history"].append({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "old_version": old_version,
            "new_version": VERSION,
            "change_type": current_changes["type"],
            "description": current_changes["description"],
            "changes": current_changes["changes"]
        })
        try:
            with open(VERSION_LOG_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            cprint(Color.GREEN, f"Detected version upgrade: {old_version} -> {VERSION}, recorded.")
        except Exception as e:
            cprint(Color.RED, f"Unable to update version log: {e}")

def show_version_history():
    from utils.lang import t
    print("\n" + t("version_history_title"))
    if not os.path.exists(VERSION_LOG_FILE):
        cprint(Color.YELLOW, t("version_no_history"))
        input(t("press_enter"))
        return
    try:
        with open(VERSION_LOG_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        history = data.get("history", [])
        if not history:
            cprint(Color.YELLOW, t("version_no_history"))
        else:
            for record in reversed(history):
                timestamp = record.get("timestamp", "Unknown time")
                old_version = record.get("old_version", "N/A")
                new_version = record.get("new_version", "Unknown")
                change_type = record.get("change_type", "Unknown type")
                description = record.get("description", "No description")
                changes = record.get("changes", [])
                changes_text = "\n".join([f"  • {change}" for change in changes])
                print(f"\n{Color.GREEN}{'='*60}{Color.END}")
                print(f"{Color.CYAN}Time:{Color.END} {timestamp}")
                print(f"{Color.CYAN}Version:{Color.END} {old_version} → {Color.GREEN}{new_version}{Color.END}")
                print(f"{Color.CYAN}Type:{Color.END} {change_type}")
                print(f"{Color.CYAN}Description:{Color.END} {description}")
                print(f"{Color.CYAN}Changes:{Color.END}")
                print(changes_text)
    except Exception as e:
        cprint(Color.RED, f"Failed to read version history: {e}")
    input(t("press_enter"))
