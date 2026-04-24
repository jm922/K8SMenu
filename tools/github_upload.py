#!/usr/bin/env python3
"""
GitHub upload tool for K8S Manager.

Features:
- Standard menu entry function
- Check git availability
- Check whether current directory is a git repository
- Show current branch and remotes
- Show git status
- Check .gitignore
- Warn about suspicious files and directories
- Confirm before add / commit / push
"""

import os
import shutil
import subprocess

from utils.color import cprint, Color


SUSPICIOUS_PATH_PREFIXES = [
    "LOG/",
    "UPGRADE_TMP/",
    "__pycache__/",
    ".trash_yaml/",
]

SUSPICIOUS_FILE_SUFFIXES = [
    ".bak",
    ".backup",
    ".pyc",
]


def _pause():
    input("\nPress Enter to continue...")


def _input_required(prompt):
    while True:
        value = input(f"{prompt}: ").strip()
        if value:
            return value
        cprint(Color.YELLOW, "Input cannot be empty.")


def _input_yes_no(prompt, default=False):
    suffix = "[Y/n]" if default else "[y/N]"
    while True:
        value = input(f"{prompt} {suffix}: ").strip().lower()
        if value == "":
            return default
        if value in ("y", "yes"):
            return True
        if value in ("n", "no"):
            return False
        cprint(Color.YELLOW, "Please enter y or n.")


def _run_cmd(cmd, cwd=None):
    """
    Run command and return:
    (ok: bool, stdout: str, stderr: str, returncode: int)
    """
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=cwd
        )
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip(), result.returncode
    except Exception as e:
        return False, "", str(e), 1


def _run_and_print(cmd, cwd=None):
    """
    Run command and print final output in a readable way.
    """
    print(f"\nCommand: {' '.join(cmd)}")
    ok, out, err, _ = _run_cmd(cmd, cwd=cwd)

    if ok:
        cprint(Color.GREEN, "Command succeeded.")
        if out:
            print(out)
    else:
        cprint(Color.RED, "Command failed.")
        if err:
            print(err)
        elif out:
            print(out)

    return ok


def _git_available():
    return shutil.which("git") is not None


def _is_git_repo(repo_dir):
    ok, _, _, _ = _run_cmd(["git", "rev-parse", "--is-inside-work-tree"], cwd=repo_dir)
    return ok


def _get_repo_root(repo_dir):
    ok, out, _, _ = _run_cmd(["git", "rev-parse", "--show-toplevel"], cwd=repo_dir)
    return out if ok and out else None


def _get_current_branch(repo_dir):
    ok, out, _, _ = _run_cmd(["git", "branch", "--show-current"], cwd=repo_dir)
    return out if ok and out else "Unknown"


def _get_remotes(repo_dir):
    ok, out, _, _ = _run_cmd(["git", "remote", "-v"], cwd=repo_dir)
    if not ok or not out:
        return []
    return out.splitlines()


def _get_git_status_short(repo_dir):
    ok, out, _, _ = _run_cmd(["git", "status", "--short"], cwd=repo_dir)
    if not ok:
        return []
    return out.splitlines() if out else []


def _get_tracked_branch(repo_dir):
    ok, out, _, _ = _run_cmd(
        ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
        cwd=repo_dir
    )
    return out if ok and out else None


def _check_gitignore(repo_dir):
    return os.path.exists(os.path.join(repo_dir, ".gitignore"))


def _find_suspicious_paths(status_lines):
    """
    Parse `git status --short` output and return suspicious entries.
    """
    suspicious = []

    for line in status_lines:
        raw = line.strip()
        if not raw:
            continue

        path = raw[3:].strip() if len(raw) >= 4 else raw
        lowered = path.lower()

        matched = False
        for prefix in SUSPICIOUS_PATH_PREFIXES:
            if lowered.startswith(prefix.lower()):
                suspicious.append(path)
                matched = True
                break

        if matched:
            continue

        for suffix in SUSPICIOUS_FILE_SUFFIXES:
            if lowered.endswith(suffix.lower()):
                suspicious.append(path)
                break

    return sorted(set(suspicious))


def _print_repo_summary(repo_dir):
    print("\n--- Git Repository Summary ---")

    repo_root = _get_repo_root(repo_dir)
    branch = _get_current_branch(repo_dir)
    remotes = _get_remotes(repo_dir)
    status_lines = _get_git_status_short(repo_dir)
    tracked_branch = _get_tracked_branch(repo_dir)
    has_gitignore = _check_gitignore(repo_dir)

    print(f"Repository root: {repo_root or 'Unknown'}")
    print(f"Current branch:  {branch}")
    print(f"Tracked branch:  {tracked_branch or 'Not configured'}")
    print(f".gitignore:      {'Present' if has_gitignore else 'Missing'}")

    print("\nRemotes:")
    if remotes:
        for line in remotes:
            print(f"  {line}")
    else:
        cprint(Color.YELLOW, "  No git remotes configured.")

    print("\nGit status:")
    if status_lines:
        for line in status_lines:
            print(f"  {line}")
    else:
        cprint(Color.GREEN, "  Working tree is clean.")

    suspicious = _find_suspicious_paths(status_lines)
    if suspicious:
        print("\nSuspicious files/directories detected:")
        for item in suspicious:
            cprint(Color.YELLOW, f"  {item}")
    else:
        print("\nSuspicious files/directories detected:")
        cprint(Color.GREEN, "  None")

    if not has_gitignore:
        cprint(Color.YELLOW, "\nWarning: .gitignore is missing.")
        cprint(Color.YELLOW, "You may accidentally commit log files, temp files, or backups.")

    return {
        "repo_root": repo_root,
        "branch": branch,
        "tracked_branch": tracked_branch,
        "remotes": remotes,
        "status_lines": status_lines,
        "has_gitignore": has_gitignore,
        "suspicious": suspicious,
    }


def _show_git_status(repo_dir):
    print("\n--- Full Git Status ---")
    _run_and_print(["git", "status"], cwd=repo_dir)
    _pause()


def _stage_changes(repo_dir):
    summary = _print_repo_summary(repo_dir)

    if not summary["status_lines"]:
        cprint(Color.YELLOW, "No modified or untracked files found.")
        _pause()
        return False

    if not _input_yes_no("Proceed with 'git add .'?", default=False):
        cprint(Color.YELLOW, "Stage operation cancelled.")
        _pause()
        return False

    ok = _run_and_print(["git", "add", "."], cwd=repo_dir)
    _pause()
    return ok


def _commit_changes(repo_dir):
    summary = _print_repo_summary(repo_dir)

    if not summary["status_lines"]:
        cprint(Color.YELLOW, "No changes detected. Nothing to commit.")
        _pause()
        return False

    message = _input_required("Enter commit message")

    if not _input_yes_no(f"Proceed with commit message '{message}'?", default=True):
        cprint(Color.YELLOW, "Commit cancelled.")
        _pause()
        return False

    ok = _run_and_print(["git", "commit", "-m", message], cwd=repo_dir)
    _pause()
    return ok


def _push_changes(repo_dir):
    summary = _print_repo_summary(repo_dir)

    if not summary["remotes"]:
        cprint(Color.RED, "No git remotes configured. Push cannot continue.")
        _pause()
        return False

    default_branch = summary["branch"] if summary["branch"] != "Unknown" else "main"
    remote_name = input("Remote name [default: origin]: ").strip() or "origin"
    branch_name = input(f"Branch name [default: {default_branch}]: ").strip() or default_branch

    print("\nPush preview:")
    print(f"  Remote: {remote_name}")
    print(f"  Branch: {branch_name}")
    print(f"  Command: git push {remote_name} {branch_name}")

    if not _input_yes_no("Proceed with push?", default=False):
        cprint(Color.YELLOW, "Push cancelled.")
        _pause()
        return False

    ok = _run_and_print(["git", "push", remote_name, branch_name], cwd=repo_dir)
    _pause()
    return ok


def _add_commit_push_flow(repo_dir):
    summary = _print_repo_summary(repo_dir)

    if not summary["status_lines"]:
        cprint(Color.YELLOW, "No local changes detected.")
        _pause()
        return

    if not _input_yes_no("Proceed with 'git add .' first?", default=True):
        cprint(Color.YELLOW, "Flow cancelled.")
        _pause()
        return

    if not _run_and_print(["git", "add", "."], cwd=repo_dir):
        _pause()
        return

    message = _input_required("Enter commit message")

    if not _run_and_print(["git", "commit", "-m", message], cwd=repo_dir):
        _pause()
        return

    if _input_yes_no("Proceed with push now?", default=True):
        summary = _print_repo_summary(repo_dir)
        if not summary["remotes"]:
            cprint(Color.RED, "No git remotes configured. Push skipped.")
            _pause()
            return

        remote_name = input("Remote name [default: origin]: ").strip() or "origin"
        default_branch = summary["branch"] if summary["branch"] != "Unknown" else "main"
        branch_name = input(f"Branch name [default: {default_branch}]: ").strip() or default_branch

        _run_and_print(["git", "push", remote_name, branch_name], cwd=repo_dir)

    _pause()


def upload_to_github_git():
    """
    Legacy-compatible entry function.
    """
    github_upload_menu()


def github_upload_menu():
    """
    Standard zero-argument menu entry for tools/system_tools.py.
    """
    repo_dir = os.getcwd()

    print("\n--- GitHub Upload ---")

    if not _git_available():
        cprint(Color.RED, "git is not installed or not found in PATH.")
        cprint(Color.YELLOW, "Please install git first.")
        _pause()
        return

    if not _is_git_repo(repo_dir):
        cprint(Color.RED, "Current directory is not a git repository.")
        cprint(Color.YELLOW, "Please run this tool inside your project git repository.")
        _pause()
        return

    while True:
        print("\n--- GitHub Upload Menu ---")
        print("1. Show repository summary")
        print("2. Show full git status")
        print("3. Stage changes (git add .)")
        print("4. Commit changes")
        print("5. Push changes")
        print("6. Add + Commit + Push workflow")
        print("7. Back (return)")

        choice = input("Choose (1-7): ").strip()

        if choice == "1":
            _print_repo_summary(repo_dir)
            _pause()
        elif choice == "2":
            _show_git_status(repo_dir)
        elif choice == "3":
            _stage_changes(repo_dir)
        elif choice == "4":
            _commit_changes(repo_dir)
        elif choice == "5":
            _push_changes(repo_dir)
        elif choice == "6":
            _add_commit_push_flow(repo_dir)
        elif choice == "7":
            break
        else:
            cprint(Color.RED, "Invalid option.")
