#!/usr/bin/env python3
"""
GitHub upload tools (Git CLI only)
"""

import os
import sys
import subprocess
from utils.color import cprint, Color
from utils.lang import t
from utils.helpers import input_yes_no, input_yes_no_text

def install_git():
    cprint(Color.BLUE, t("git_installing"))
    try:
        if os.path.exists('/usr/bin/apt-get'):
            subprocess.run(['sudo', 'apt-get', 'update'], check=True)
            subprocess.run(['sudo', 'apt-get', 'install', '-y', 'git'], check=True)
        elif os.path.exists('/usr/bin/yum'):
            subprocess.run(['sudo', 'yum', 'install', '-y', 'git'], check=True)
        elif os.path.exists('/usr/bin/dnf'):
            subprocess.run(['sudo', 'dnf', 'install', '-y', 'git'], check=True)
        elif os.path.exists('/usr/bin/pacman'):
            subprocess.run(['sudo', 'pacman', '-S', '--noconfirm', 'git'], check=True)
        else:
            cprint(Color.RED, "Unknown package manager. Please install git manually.")
            return False
        cprint(Color.GREEN, t("git_install_success"))
        return True
    except subprocess.CalledProcessError:
        cprint(Color.RED, t("git_install_failed"))
        return False

def upload_to_github_git():
    print("\n" + t("git_upload_title"))

    # Check git installation
    cprint(Color.BLUE, t("git_check_install"))
    try:
        subprocess.run(['git', '--version'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        cprint(Color.YELLOW, t("git_not_installed"))
        if input_yes_no("git_install_prompt", default=False):
            if not install_git():
                input(t("press_enter"))
                return
        else:
            return

    current_file = os.path.abspath(sys.argv[0])
    current_dir = os.path.dirname(current_file)
    os.chdir(current_dir)

    # Initialize git repo if needed
    cprint(Color.BLUE, t("git_check_repo"))
    result = subprocess.run(['git', 'rev-parse', '--git-dir'], capture_output=True, text=True)
    if result.returncode != 0:
        cprint(Color.YELLOW, "Not a git repository. Initializing...")
        init_result = subprocess.run(['git', 'init'], capture_output=True, text=True)
        if init_result.returncode == 0:
            cprint(Color.GREEN, t("git_init_success"))
        else:
            cprint(Color.RED, f"Failed to initialize git: {init_result.stderr}")
            input(t("press_enter"))
            return

    # Check remote origin
    cprint(Color.BLUE, t("git_remote_check"))
    remote_result = subprocess.run(['git', 'remote', 'get-url', 'origin'], capture_output=True, text=True)
    if remote_result.returncode != 0:
        cprint(Color.YELLOW, "No remote origin configured.")
        repo_url = input(t("git_remote_prompt")).strip()
        if not repo_url:
            cprint(Color.RED, "Repository URL is required.")
            input(t("press_enter"))
            return
        add_remote = subprocess.run(['git', 'remote', 'add', 'origin', repo_url], capture_output=True, text=True)
        if add_remote.returncode == 0:
            cprint(Color.GREEN, t("git_remote_success"))
        else:
            cprint(Color.RED, f"Failed to add remote: {add_remote.stderr}")
            input(t("press_enter"))
            return
    else:
        cprint(Color.GREEN, f"Remote origin: {remote_result.stdout.strip()}")

    # Show changes and confirm
    status_result = subprocess.run(['git', 'status', '--porcelain'], capture_output=True, text=True)
    if not status_result.stdout.strip():
        cprint(Color.YELLOW, "No changes detected. Nothing to commit.")
        # Still try to push (maybe only remote is behind)
        branch_result = subprocess.run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], capture_output=True, text=True)
        current_branch = branch_result.stdout.strip() if branch_result.returncode == 0 else "main"
        push_result = subprocess.run(['git', 'push', '-u', 'origin', current_branch], capture_output=True, text=True)
        if push_result.returncode == 0:
            if "Everything up-to-date" in push_result.stdout:
                cprint(Color.GREEN, t("git_up_to_date"))
            else:
                cprint(Color.GREEN, t("git_push_success"))
        else:
            cprint(Color.RED, t("git_push_fail", error=push_result.stderr))
        input(t("press_enter"))
        return

    print("\n" + "Files to be added/committed:")
    print(status_result.stdout)
    if not input_yes_no_text("Continue with adding all changes?", default=True):
        cprint(Color.YELLOW, "Upload cancelled.")
        input(t("press_enter"))
        return

    # Add all changes
    cprint(Color.BLUE, "Adding all changes to Git...")
    add_result = subprocess.run(['git', 'add', '.'], capture_output=True, text=True)
    if add_result.returncode != 0:
        cprint(Color.RED, f"Failed to add files: {add_result.stderr}")
        input(t("press_enter"))
        return
    cprint(Color.GREEN, "✅ Files added.")

    # Configure git user if needed
    cprint(Color.BLUE, t("git_identity_check"))
    user_name = subprocess.run(['git', 'config', 'user.name'], capture_output=True, text=True).stdout.strip()
    user_email = subprocess.run(['git', 'config', 'user.email'], capture_output=True, text=True).stdout.strip()
    if not user_name or not user_email:
        cprint(Color.YELLOW, t("git_identity_missing"))
        print("Please provide the following information (this will be stored locally for this repository):")
        if not user_name:
            new_name = input(t("git_identity_name_prompt")).strip()
            if new_name:
                subprocess.run(['git', 'config', 'user.name', new_name], check=True)
        if not user_email:
            new_email = input(t("git_identity_email_prompt")).strip()
            if new_email:
                subprocess.run(['git', 'config', 'user.email', new_email], check=True)
        cprint(Color.GREEN, t("git_identity_success"))

    # Commit with version info
    from version import VERSION
    default_msg = f"Upload version {VERSION}"
    commit_msg = input(t("git_commit_message", filename="project")).strip()
    if not commit_msg:
        commit_msg = default_msg
    commit_result = subprocess.run(['git', 'commit', '-m', commit_msg], capture_output=True, text=True)
    if commit_result.returncode != 0:
        cprint(Color.RED, f"Commit failed: {commit_result.stderr}")
        input(t("press_enter"))
        return
    cprint(Color.GREEN, t("git_commit_success"))

    # Push
    branch_result = subprocess.run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], capture_output=True, text=True)
    current_branch = branch_result.stdout.strip() if branch_result.returncode == 0 else "main"
    cprint(Color.BLUE, t("git_push"))
    push_result = subprocess.run(['git', 'push', '-u', 'origin', current_branch], capture_output=True, text=True)
    if push_result.returncode == 0:
        cprint(Color.GREEN, t("git_push_success"))
    else:
        cprint(Color.RED, t("git_push_fail", error=push_result.stderr))
        if "failed to push" in push_result.stderr.lower() or "rejected" in push_result.stderr.lower():
            cprint(Color.YELLOW, "You may need to pull remote changes first: git pull origin " + current_branch)

    input(t("press_enter"))
