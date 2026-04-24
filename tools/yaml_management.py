#!/usr/bin/env python3
"""
YAML workspace for K8S Manager.

Features:
- List local YAML files with parsed summary
- Support multi-document YAML
- View full YAML content
- Validate YAML syntax
- Validate with kubectl dry-run
- Apply one YAML file or all YAML files
- Safe delete to .trash_yaml instead of permanent removal
"""

import glob
import os
import shutil
import subprocess
from datetime import datetime

import yaml

from utils.color import cprint, Color


TRASH_DIR_NAME = ".trash_yaml"


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


def _truncate(text, length):
    text = "" if text is None else str(text)
    if len(text) <= length:
        return text
    return text[: length - 3] + "..."


def _human_size(num_bytes):
    if num_bytes < 1024:
        return f"{num_bytes} B"
    if num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} KB"
    return f"{num_bytes / (1024 * 1024):.1f} MB"


def _get_yaml_files():
    files = glob.glob("*.yaml") + glob.glob("*.yml")
    files = sorted(set(files))
    return files


def _load_yaml_documents(file_path):
    """
    Return:
    - ok: bool
    - docs: list
    - error: str | None
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            docs = list(yaml.safe_load_all(f))
        return True, docs, None
    except Exception as e:
        return False, [], str(e)


def _extract_doc_summary(doc):
    """
    Return a short summary for one YAML document.
    """
    if doc is None:
        return "Empty document"

    if not isinstance(doc, dict):
        return f"Non-dict document ({type(doc).__name__})"

    api_version = doc.get("apiVersion", "N/A")
    kind = doc.get("kind", "Unknown")
    metadata = doc.get("metadata", {}) if isinstance(doc.get("metadata", {}), dict) else {}
    name = metadata.get("name", "Unnamed")
    namespace = metadata.get("namespace", "default")

    summary = f"{kind}/{name} [{namespace}] ({api_version})"
    return summary


def _extract_file_summary(file_path):
    """
    Return a compact file-level summary.
    """
    ok, docs, error = _load_yaml_documents(file_path)
    if not ok:
        return {
            "parse_ok": False,
            "doc_count": 0,
            "summary": f"PARSE ERROR: {_truncate(error, 60)}",
            "details": [],
        }

    non_empty_docs = [doc for doc in docs if doc is not None]
    details = [_extract_doc_summary(doc) for doc in non_empty_docs]

    if not non_empty_docs:
        return {
            "parse_ok": True,
            "doc_count": 0,
            "summary": "Empty YAML",
            "details": [],
        }

    if len(details) == 1:
        summary = details[0]
    elif len(details) == 2:
        summary = f"{details[0]} | {details[1]}"
    else:
        summary = f"{details[0]} | {details[1]} | +{len(details) - 2} more"

    return {
        "parse_ok": True,
        "doc_count": len(non_empty_docs),
        "summary": summary,
        "details": details,
    }


def _validate_yaml_syntax(file_path):
    ok, _, error = _load_yaml_documents(file_path)
    return ok, error


def _validate_with_kubectl(file_path):
    result = subprocess.run(
        ["kubectl", "apply", "--dry-run=client", "-f", file_path],
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        return True, result.stdout.strip()
    return False, (result.stderr or result.stdout).strip()


def _apply_yaml_file(file_path):
    result = subprocess.run(
        ["kubectl", "apply", "-f", file_path],
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        return True, result.stdout.strip()
    return False, (result.stderr or result.stdout).strip()


def _ensure_trash_dir():
    trash_dir = os.path.join(os.getcwd(), TRASH_DIR_NAME)
    os.makedirs(trash_dir, exist_ok=True)
    return trash_dir


def _safe_delete_file(file_path):
    """
    Move file into local trash directory instead of permanent deletion.
    """
    trash_dir = _ensure_trash_dir()

    base_name = os.path.basename(file_path)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target_name = f"{timestamp}_{base_name}"
    target_path = os.path.join(trash_dir, target_name)

    shutil.move(file_path, target_path)
    return target_path


def _empty_trash():
    trash_dir = os.path.join(os.getcwd(), TRASH_DIR_NAME)
    if not os.path.isdir(trash_dir):
        cprint(Color.YELLOW, "Trash directory does not exist.")
        return

    entries = os.listdir(trash_dir)
    if not entries:
        cprint(Color.YELLOW, "Trash directory is already empty.")
        return

    if not _input_yes_no("Permanently delete all files in YAML trash?", default=False):
        cprint(Color.YELLOW, "Trash purge cancelled.")
        return

    deleted = 0
    failed = 0

    for name in entries:
        path = os.path.join(trash_dir, name)
        try:
            if os.path.isfile(path) or os.path.islink(path):
                os.unlink(path)
            elif os.path.isdir(path):
                shutil.rmtree(path)
            deleted += 1
        except Exception:
            failed += 1

    cprint(Color.GREEN, f"Deleted from trash: {deleted}")
    if failed > 0:
        cprint(Color.RED, f"Failed to delete: {failed}")


def list_yaml_files():
    """
    Show YAML files with parsed summary and return:
    - files: list[str]
    - file_map: dict[str, str]
    """
    yaml_files = _get_yaml_files()

    print("\n--- YAML Workspace: Local YAML Files ---")

    if not yaml_files:
        cprint(Color.YELLOW, "No YAML files found in the current directory.")
        return [], {}

    print(
        f"{Color.BOLD}{Color.CYAN}"
        f"{'#':<4} {'File Name':<30} {'Size':<10} {'Docs':<6} {'Modified':<18} {'Summary':<70}"
        f"{Color.END}"
    )
    print("-" * 150)

    file_map = {}

    for idx, file_name in enumerate(yaml_files, 1):
        try:
            size = _human_size(os.path.getsize(file_name))
        except Exception:
            size = "N/A"

        try:
            modified = datetime.fromtimestamp(
                os.path.getmtime(file_name)
            ).strftime("%Y-%m-%d %H:%M")
        except Exception:
            modified = "Unknown"

        summary_info = _extract_file_summary(file_name)
        doc_count = summary_info["doc_count"]
        summary = _truncate(summary_info["summary"], 70)

        color = Color.GREEN if summary_info["parse_ok"] else Color.YELLOW

        print(
            f"{Color.GREEN}{idx:<4}{Color.END} "
            f"{file_name:<30} "
            f"{size:<10} "
            f"{str(doc_count):<6} "
            f"{modified:<18} "
            f"{color}{summary}{Color.END}"
        )

        file_map[str(idx)] = file_name
        file_map[file_name] = file_name

    return yaml_files, file_map


def _resolve_file_identifier(identifier, file_map):
    return file_map.get(identifier)


def view_yaml_file():
    yaml_files, file_map = list_yaml_files()
    if not yaml_files:
        _pause()
        return

    identifier = _input_required("Enter YAML file number or name to view")
    file_name = _resolve_file_identifier(identifier, file_map)

    if not file_name:
        cprint(Color.RED, f"YAML file not found: {identifier}")
        _pause()
        return

    print(f"\n--- Full YAML Content: {file_name} ---")
    print("=" * 80)

    try:
        with open(file_name, "r", encoding="utf-8") as f:
            print(f.read())
    except Exception as e:
        cprint(Color.RED, f"Failed to read file: {e}")

    print("=" * 80)
    _pause()


def show_yaml_file_details():
    yaml_files, file_map = list_yaml_files()
    if not yaml_files:
        _pause()
        return

    identifier = _input_required("Enter YAML file number or name to inspect")
    file_name = _resolve_file_identifier(identifier, file_map)

    if not file_name:
        cprint(Color.RED, f"YAML file not found: {identifier}")
        _pause()
        return

    summary_info = _extract_file_summary(file_name)

    print(f"\n--- YAML File Details: {file_name} ---")

    if not summary_info["parse_ok"]:
        cprint(Color.RED, summary_info["summary"])
        _pause()
        return

    if not summary_info["details"]:
        cprint(Color.YELLOW, "This YAML file is empty.")
        _pause()
        return

    for idx, detail in enumerate(summary_info["details"], 1):
        print(f"{idx}. {detail}")

    _pause()


def _choose_file_scope(action_name):
    print(f"\n--- {action_name} ---")
    print("1. One YAML file")
    print("2. All YAML files in current directory")
    print("3. Back")
    choice = input("Choose (1-3): ").strip()
    return choice


def _select_single_yaml_file():
    yaml_files, file_map = list_yaml_files()
    if not yaml_files:
        return None

    identifier = _input_required("Enter YAML file number or name")
    file_name = _resolve_file_identifier(identifier, file_map)

    if not file_name:
        cprint(Color.RED, f"YAML file not found: {identifier}")
        return None

    return [file_name]


def _select_all_yaml_files():
    yaml_files = _get_yaml_files()
    if not yaml_files:
        cprint(Color.YELLOW, "No YAML files found in the current directory.")
        return None
    return yaml_files


def _run_on_yaml_scope(action_name):
    choice = _choose_file_scope(action_name)

    if choice == "1":
        return _select_single_yaml_file()
    if choice == "2":
        return _select_all_yaml_files()
    return None


def validate_yaml_syntax_menu():
    files = _run_on_yaml_scope("Validate YAML Syntax")
    if not files:
        _pause()
        return

    print("\n--- YAML Syntax Validation Result ---")

    passed = 0
    failed = 0

    for file_name in files:
        ok, error = _validate_yaml_syntax(file_name)
        if ok:
            cprint(Color.GREEN, f"PASS  | {file_name}")
            passed += 1
        else:
            cprint(Color.RED, f"FAIL  | {file_name}")
            print(f"       {error}")
            failed += 1

    print("\nSummary:")
    cprint(Color.GREEN, f"Passed: {passed}")
    if failed > 0:
        cprint(Color.RED, f"Failed: {failed}")

    _pause()


def validate_kubectl_dry_run_menu():
    files = _run_on_yaml_scope("Validate with kubectl dry-run")
    if not files:
        _pause()
        return

    print("\n--- kubectl Dry-Run Validation Result ---")

    passed = 0
    failed = 0

    for file_name in files:
        ok, output = _validate_with_kubectl(file_name)
        if ok:
            cprint(Color.GREEN, f"PASS  | {file_name}")
            if output:
                print(f"       {output}")
            passed += 1
        else:
            cprint(Color.RED, f"FAIL  | {file_name}")
            if output:
                print(f"       {output}")
            failed += 1

    print("\nSummary:")
    cprint(Color.GREEN, f"Passed: {passed}")
    if failed > 0:
        cprint(Color.RED, f"Failed: {failed}")

    _pause()


def apply_yaml_menu():
    files = _run_on_yaml_scope("Apply YAML")
    if not files:
        _pause()
        return

    if _input_yes_no("Run kubectl dry-run validation before apply?", default=True):
        validation_failed = False
        print("\n--- Pre-Apply Dry-Run Validation ---")
        for file_name in files:
            ok, output = _validate_with_kubectl(file_name)
            if ok:
                cprint(Color.GREEN, f"PASS  | {file_name}")
            else:
                cprint(Color.RED, f"FAIL  | {file_name}")
                if output:
                    print(f"       {output}")
                validation_failed = True

        if validation_failed:
            cprint(Color.YELLOW, "Apply aborted because one or more files failed dry-run validation.")
            _pause()
            return

    print("\nFiles selected for apply:")
    for file_name in files:
        print(f"  - {file_name}")

    if not _input_yes_no("Proceed with kubectl apply?", default=False):
        cprint(Color.YELLOW, "Apply cancelled.")
        _pause()
        return

    print("\n--- Apply Result ---")

    success = 0
    failed = 0

    for file_name in files:
        ok, output = _apply_yaml_file(file_name)
        if ok:
            cprint(Color.GREEN, f"APPLIED | {file_name}")
            if output:
                print(f"         {output}")
            success += 1
        else:
            cprint(Color.RED, f"FAILED  | {file_name}")
            if output:
                print(f"         {output}")
            failed += 1

    print("\nSummary:")
    cprint(Color.GREEN, f"Applied successfully: {success}")
    if failed > 0:
        cprint(Color.RED, f"Failed: {failed}")

    _pause()


def safe_delete_yaml_menu():
    yaml_files, file_map = list_yaml_files()
    if not yaml_files:
        _pause()
        return

    print("\nEnter one or more file numbers/names separated by spaces.")
    print("Example: 1 3 5")
    print("Enter 'q' to cancel.")

    raw = input("Select YAML files to move into trash: ").strip()
    if not raw or raw.lower() in ("q", "quit"):
        cprint(Color.YELLOW, "Delete cancelled.")
        _pause()
        return

    selected = []
    invalid = []

    for part in raw.split():
        file_name = _resolve_file_identifier(part, file_map)
        if file_name:
            if file_name not in selected:
                selected.append(file_name)
        else:
            invalid.append(part)

    if invalid:
        cprint(Color.RED, f"Invalid selections: {', '.join(invalid)}")

    if not selected:
        cprint(Color.YELLOW, "No valid YAML files selected.")
        _pause()
        return

    print("\nSelected files:")
    for file_name in selected:
        print(f"  - {file_name}")

    if not _input_yes_no("Move selected files to YAML trash?", default=False):
        cprint(Color.YELLOW, "Delete cancelled.")
        _pause()
        return

    moved = 0
    failed = 0

    for file_name in selected:
        try:
            target_path = _safe_delete_file(file_name)
            cprint(Color.GREEN, f"MOVED  | {file_name}")
            print(f"         -> {target_path}")
            moved += 1
        except Exception as e:
            cprint(Color.RED, f"FAILED | {file_name}")
            print(f"         -> {e}")
            failed += 1

    print("\nSummary:")
    cprint(Color.GREEN, f"Moved to trash: {moved}")
    if failed > 0:
        cprint(Color.RED, f"Failed: {failed}")

    _pause()


def yaml_file_management():
    """
    YAML workspace main menu.
    """
    while True:
        print("\n--- YAML Management Workspace ---")
        print("1. List YAML files (summary)")
        print("2. Show YAML file details (kind/name/namespace)")
        print("3. View full YAML content")
        print("4. Validate YAML syntax")
        print("5. Validate with kubectl dry-run")
        print("6. Apply YAML")
        print("7. Safe delete YAML file(s)")
        print("8. Empty YAML trash")
        print("9. Back (return)")

        choice = input("Choose (1-9): ").strip()

        if choice == "1":
            list_yaml_files()
            _pause()
        elif choice == "2":
            show_yaml_file_details()
        elif choice == "3":
            view_yaml_file()
        elif choice == "4":
            validate_yaml_syntax_menu()
        elif choice == "5":
            validate_kubectl_dry_run_menu()
        elif choice == "6":
            apply_yaml_menu()
        elif choice == "7":
            safe_delete_yaml_menu()
        elif choice == "8":
            _empty_trash()
            _pause()
        elif choice == "9":
            break
        else:
            cprint(Color.RED, "Invalid option.")


def yaml_management_menu():
    """
    Standard zero-argument entry for tools/system_tools.py.
    """
    yaml_file_management()
