#!/usr/bin/env python3
"""
Program upgrade tool

Features:
- Upgrade .py files from UPGRADE_TMP
- Automatic backup and rollback
- Pre-check / dry-run mode
- Stronger post-upgrade health check
- Recursive scan of UPGRADE_TMP for .py files
- Flat target matching by filename in project root
"""

import os
import sys
import time
import shutil
import py_compile
import subprocess
from collections import Counter
from datetime import datetime

from utils.color import cprint, Color
from utils.lang import t
from utils.helpers import input_yes_no_text


SHORT_DELAY = 0.6
MEDIUM_DELAY = 1.2


def short_pause():
    time.sleep(SHORT_DELAY)


def medium_pause():
    time.sleep(MEDIUM_DELAY)


def section(title):
    print("\n" + "=" * 60)
    cprint(Color.BOLD, title)
    print("=" * 60)


def setup_log_dir():
    """Create LOG directory if not exists, return log file path"""
    base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    log_dir = os.path.join(base_dir, "LOG")
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        cprint(Color.BLUE, f"Created log directory: {log_dir}")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f"upgrade_{timestamp}.log")
    return log_file


def write_log(log_file, message, level="INFO"):
    """Write message to log file and also print to console"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] [{level}] {message}"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(log_line + "\n")

    if level == "ERROR":
        cprint(Color.RED, message)
    elif level == "WARNING":
        cprint(Color.YELLOW, message)
    else:
        cprint(Color.BLUE, message)


def collect_upgrade_files(upgrade_dir):
    """
    Recursively collect .py files from UPGRADE_TMP.
    Returns list of dicts with:
      - src_path
      - rel_path
      - filename
    """
    results = []
    for root, dirs, files in os.walk(upgrade_dir):
        dirs[:] = [d for d in dirs if d not in {".git", "__pycache__"}]
        for file in files:
            if file.endswith(".py"):
                src_path = os.path.join(root, file)
                rel_path = os.path.relpath(src_path, upgrade_dir)
                results.append(
                    {
                        "src_path": src_path,
                        "rel_path": rel_path,
                        "filename": file,
                    }
                )
    return sorted(results, key=lambda x: x["rel_path"])


def find_target_file(base_dir, filename, exclude_dir):
    """
    Recursively search for a file with given filename in base_dir,
    excluding exclude_dir and its contents.
    Returns list of found paths.
    """
    matches = []
    exclude_abs = os.path.abspath(exclude_dir)

    for root, dirs, files in os.walk(base_dir):
        dirs[:] = [
            d for d in dirs
            if os.path.abspath(os.path.join(root, d)) != exclude_abs
            and not os.path.abspath(os.path.join(root, d)).startswith(exclude_abs + os.sep)
            and d not in {".git", "__pycache__", "LOG"}
        ]

        if filename in files:
            matches.append(os.path.join(root, filename))

    return matches


def check_python_syntax(file_path):
    """Return (True, None) or (False, error_message)"""
    try:
        py_compile.compile(file_path, doraise=True)
        return True, None
    except Exception as e:
        return False, str(e)


def path_to_module(base_dir, file_path):
    """
    Convert a Python file path to an importable module path.
    Returns None if not importable as a normal module path.
    """
    rel_path = os.path.relpath(file_path, base_dir)
    if not rel_path.endswith(".py"):
        return None

    module_path = rel_path[:-3]
    parts = module_path.split(os.sep)

    if parts[-1] == "__init__":
        parts = parts[:-1]

    if not parts:
        return None

    for p in parts:
        if not p.isidentifier():
            return None

    return ".".join(parts)


def backup_file(file_path, log_file):
    """Backup a file to file_path.bak, return (success, backup_path)"""
    backup_path = file_path + ".bak"
    try:
        shutil.copy2(file_path, backup_path)
        write_log(log_file, f"Backed up {file_path} -> {backup_path}")
        return True, backup_path
    except Exception as e:
        write_log(log_file, f"Failed to backup {file_path}: {e}", "ERROR")
        return False, None


def restore_backup(file_path, log_file):
    """Restore from backup file"""
    backup_path = file_path + ".bak"
    if os.path.exists(backup_path):
        try:
            shutil.copy2(backup_path, file_path)
            write_log(log_file, f"Restored backup {backup_path} -> {file_path}")
            return True
        except Exception as e:
            write_log(log_file, f"Failed to restore backup {backup_path}: {e}", "ERROR")
    return False


def rollback_all(upgraded_records, log_file):
    """Rollback all upgraded files using their backup files"""
    success = True
    section("ROLLBACK")
    for record in upgraded_records:
        dest_path = record["dest_path"]
        backup_path = record["backup_path"]

        if os.path.exists(backup_path):
            try:
                shutil.copy2(backup_path, dest_path)
                write_log(log_file, f"Rolled back {dest_path} from {backup_path}")
            except Exception as e:
                write_log(log_file, f"Failed to rollback {dest_path}: {e}", "ERROR")
                success = False
        else:
            write_log(log_file, f"Backup not found for {dest_path}, cannot rollback", "ERROR")
            success = False
    return success


def precheck_upgrade_plan(base_dir, upgrade_dir, log_file):
    """
    Build upgrade plan with pre-check results.
    Status values:
      - READY
      - SOURCE_SYNTAX_ERROR
      - TARGET_NOT_FOUND
      - MULTIPLE_TARGETS
      - DUPLICATE_SOURCE_FILENAME
    """
    source_files = collect_upgrade_files(upgrade_dir)
    if not source_files:
        return []

    filename_counts = Counter(item["filename"] for item in source_files)
    plan = []

    for item in source_files:
        src_path = item["src_path"]
        rel_path = item["rel_path"]
        filename = item["filename"]

        syntax_ok, syntax_err = check_python_syntax(src_path)
        matches = []
        status = "READY"
        reason = ""

        if not syntax_ok:
            status = "SOURCE_SYNTAX_ERROR"
            reason = syntax_err
        elif filename_counts[filename] > 1:
            status = "DUPLICATE_SOURCE_FILENAME"
            reason = "Same filename appears more than once in UPGRADE_TMP"
        else:
            matches = find_target_file(base_dir, filename, upgrade_dir)
            if not matches:
                status = "TARGET_NOT_FOUND"
                reason = "Target file not found in project tree"
            elif len(matches) > 1:
                status = "MULTIPLE_TARGETS"
                reason = f"Multiple target matches found: {matches}"

        dest_path = matches[0] if status == "READY" and matches else None

        plan.append(
            {
                "src_path": src_path,
                "rel_path": rel_path,
                "filename": filename,
                "dest_path": dest_path,
                "matches": matches,
                "status": status,
                "reason": reason,
            }
        )

    write_log(log_file, f"Pre-check completed. Total source files: {len(plan)}")
    return plan


def display_precheck_summary(plan):
    """Pretty print pre-check result summary"""
    section("PRE-CHECK SUMMARY")

    ready = [p for p in plan if p["status"] == "READY"]
    syntax_errors = [p for p in plan if p["status"] == "SOURCE_SYNTAX_ERROR"]
    missing = [p for p in plan if p["status"] == "TARGET_NOT_FOUND"]
    multiple = [p for p in plan if p["status"] == "MULTIPLE_TARGETS"]
    dup_src = [p for p in plan if p["status"] == "DUPLICATE_SOURCE_FILENAME"]

    cprint(Color.GREEN, f"READY: {len(ready)}")
    cprint(Color.RED, f"SOURCE_SYNTAX_ERROR: {len(syntax_errors)}")
    cprint(Color.YELLOW, f"TARGET_NOT_FOUND: {len(missing)}")
    cprint(Color.YELLOW, f"MULTIPLE_TARGETS: {len(multiple)}")
    cprint(Color.YELLOW, f"DUPLICATE_SOURCE_FILENAME: {len(dup_src)}")

    print("\nDetailed plan:")
    for idx, item in enumerate(plan, 1):
        status = item["status"]
        rel_path = item["rel_path"]
        dest_path = item["dest_path"]

        if status == "READY":
            cprint(Color.GREEN, f"[{idx}] READY  | {rel_path}")
            print(f"      -> {dest_path}")
        elif status == "SOURCE_SYNTAX_ERROR":
            cprint(Color.RED, f"[{idx}] ERROR  | {rel_path}")
            print(f"      -> {item['reason']}")
        else:
            cprint(Color.YELLOW, f"[{idx}] SKIP   | {rel_path}")
            print(f"      -> {item['reason']}")


def run_import_check(base_dir, module_name, log_file):
    """Import a module in a clean subprocess"""
    code = (
        "import sys, importlib; "
        "sys.path.insert(0, '.'); "
        "importlib.import_module(sys.argv[1]); "
        "print('Import OK:', sys.argv[1])"
    )
    result = subprocess.run(
        [sys.executable, "-c", code, module_name],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=base_dir,
    )

    if result.returncode == 0:
        write_log(log_file, f"Import check passed: {module_name}")
        return True, None

    err = (result.stderr or result.stdout).strip()
    write_log(log_file, f"Import check failed: {module_name} -> {err}", "ERROR")
    return False, err


def run_smoke_check(base_dir, log_file):
    """Run a small smoke test for core program startup"""
    code = (
        "import sys; "
        "sys.path.insert(0, '.'); "
        "import main; "
        "from version import VERSION; "
        "print('Smoke check passed:', VERSION)"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=base_dir,
    )

    if result.returncode == 0:
        write_log(log_file, "Smoke check passed.")
        return True, None

    err = (result.stderr or result.stdout).strip()
    write_log(log_file, f"Smoke check failed: {err}", "ERROR")
    return False, err


def test_new_program(base_dir, log_file, upgraded_records):
    """
    Perform stronger post-upgrade health check.

    Checks:
    1. py_compile on upgraded target files
    2. import checks on key modules + upgraded modules
    3. smoke check on main program
    """
    section("POST-UPGRADE HEALTH CHECK")
    write_log(log_file, "Performing post-upgrade health check...")

    target_files = [r["dest_path"] for r in upgraded_records]

    cprint(Color.BLUE, "Step 1/3: Compiling upgraded target files...")
    short_pause()

    for file_path in target_files:
        ok, err = check_python_syntax(file_path)
        if not ok:
            write_log(log_file, f"Compile check failed for {file_path}: {err}", "ERROR")
            return False, f"Compile check failed for {file_path}: {err}"

    cprint(Color.GREEN, "✅ Compile check passed.")

    cprint(Color.BLUE, "Step 2/3: Running module import checks...")
    short_pause()

    modules_to_check = {"main", "version", "utils.color"}
    for file_path in target_files:
        mod = path_to_module(base_dir, file_path)
        if mod:
            modules_to_check.add(mod)

    for mod in sorted(modules_to_check):
        ok, err = run_import_check(base_dir, mod, log_file)
        if not ok:
            return False, f"Import check failed for module '{mod}': {err}"

    cprint(Color.GREEN, "✅ Import checks passed.")

    cprint(Color.BLUE, "Step 3/3: Running smoke check...")
    short_pause()

    ok, err = run_smoke_check(base_dir, log_file)
    if not ok:
        return False, f"Smoke check failed: {err}"

    cprint(Color.GREEN, "✅ Smoke check passed.")
    cprint(Color.GREEN, "✅ New program is healthy.")
    write_log(log_file, "Health check succeeded.")
    return True, None


def cleanup_upgrade_tmp(upgrade_dir, log_file):
    """Clear UPGRADE_TMP contents but keep the directory itself"""
    try:
        for item in os.listdir(upgrade_dir):
            item_path = os.path.join(upgrade_dir, item)
            if os.path.isfile(item_path) or os.path.islink(item_path):
                os.unlink(item_path)
            elif os.path.isdir(item_path):
                shutil.rmtree(item_path)

        write_log(log_file, f"Cleared contents of UPGRADE_TMP directory: {upgrade_dir}")
        cprint(Color.GREEN, "✅ UPGRADE_TMP directory cleared (directory kept).")
        return True
    except Exception as e:
        write_log(log_file, f"Failed to clear UPGRADE_TMP directory: {e}", "WARNING")
        cprint(Color.YELLOW, f"⚠️ Could not clear UPGRADE_TMP directory: {e}")
        return False


def program_upgrade():
    print("\n" + t("upgrade_title"))
    base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    upgrade_dir = os.path.join(base_dir, "UPGRADE_TMP")

    if not os.path.isdir(upgrade_dir):
        cprint(Color.RED, "UPGRADE_TMP directory not found in project root.")
        cprint(Color.YELLOW, "Please place the new version files in a folder named 'UPGRADE_TMP'.")
        input(t("press_enter"))
        return

    log_file = setup_log_dir()
    write_log(log_file, f"=== Upgrade started from {upgrade_dir} ===")

    section("UPGRADE MODE")
    dry_run = input_yes_no_text(
        "Run pre-check only (dry-run, no files will be changed)?",
        default=False
    )
    medium_pause()

    plan = precheck_upgrade_plan(base_dir, upgrade_dir, log_file)
    if not plan:
        write_log(log_file, "No .py files found in UPGRADE_TMP.", "WARNING")
        cprint(Color.YELLOW, "No .py files found in UPGRADE_TMP.")
        input(t("press_enter"))
        return

    display_precheck_summary(plan)
    medium_pause()

    ready_plan = [p for p in plan if p["status"] == "READY"]

    if not ready_plan:
        write_log(log_file, "No READY files after pre-check. Upgrade aborted.", "ERROR")
        cprint(Color.RED, "No READY files after pre-check. Upgrade aborted.")
        input(t("press_enter"))
        return

    if dry_run:
        section("DRY-RUN RESULT")
        cprint(Color.GREEN, f"Dry-run completed. READY files: {len(ready_plan)}")
        cprint(Color.YELLOW, "No files were changed.")
        input(t("press_enter"))
        return

    if not input_yes_no_text("Proceed with upgrade for READY files only?", default=False):
        cprint(Color.YELLOW, "Upgrade cancelled.")
        input(t("press_enter"))
        return

    section("UPGRADE EXECUTION")
    total = len(ready_plan)
    write_log(log_file, f"Starting upgrade execution for {total} READY file(s).")

    success_count = 0
    fail_count = 0
    upgraded_records = []

    for idx, item in enumerate(ready_plan, 1):
        src_full = item["src_path"]
        filename = item["filename"]
        dest_path = item["dest_path"]

        print(f"\n[{idx}/{total}] Processing: {filename}")
        print(f"Source: {item['rel_path']}")
        print(f"Target: {dest_path}")
        short_pause()

        backup_success, backup_path = backup_file(dest_path, log_file)
        if not backup_success:
            cprint(Color.RED, "  ❌ Backup failed, skipping.")
            fail_count += 1
            short_pause()
            continue

        try:
            orig_stat = os.stat(dest_path)
            orig_mode = orig_stat.st_mode
            write_log(log_file, f"Original permissions: {oct(orig_mode)}")
        except Exception:
            orig_mode = None

        try:
            shutil.copy2(src_full, dest_path)
            write_log(log_file, f"Copied {src_full} -> {dest_path}")
        except Exception as e:
            write_log(log_file, f"Copy failed: {e}", "ERROR")
            restore_backup(dest_path, log_file)
            fail_count += 1
            short_pause()
            continue

        if orig_mode is not None:
            try:
                os.chmod(dest_path, orig_mode)
                write_log(log_file, f"Restored permissions to {oct(orig_mode)}")
            except Exception as e:
                write_log(log_file, f"Failed to restore permissions: {e}", "WARNING")
                cprint(Color.YELLOW, "  ⚠️ Could not restore permissions")
        else:
            try:
                os.chmod(dest_path, 0o644)
                write_log(log_file, "Set default permissions (644)")
            except Exception as e:
                write_log(log_file, f"Failed to set default permissions: {e}", "WARNING")

        upgraded_records.append(
            {
                "dest_path": dest_path,
                "backup_path": backup_path,
                "filename": filename,
            }
        )
        success_count += 1
        cprint(Color.GREEN, f"  ✅ Successfully upgraded {filename}")
        short_pause()

    section("UPGRADE COPY SUMMARY")
    cprint(Color.GREEN, f"✅ Successfully copied: {success_count}")
    if fail_count > 0:
        cprint(Color.RED, f"❌ Failed: {fail_count}")

    if success_count == 0:
        write_log(log_file, "No files upgraded. Aborting.", "ERROR")
        cprint(Color.RED, "No files upgraded. Upgrade aborted.")
        input(t("press_enter"))
        return

    healthy, error_msg = test_new_program(base_dir, log_file, upgraded_records)

    if not healthy:
        cprint(Color.RED, "\n❌ Health check FAILED!")
        cprint(Color.YELLOW, f"Error: {error_msg[:500]}")
        write_log(log_file, "Health check failed. Initiating rollback...", "ERROR")
        cprint(Color.YELLOW, "Rolling back all upgraded files...")
        rollback_ok = rollback_all(upgraded_records, log_file)
        if rollback_ok:
            cprint(Color.GREEN, "✅ Rollback completed.")
        else:
            cprint(Color.RED, "⚠️ Rollback incomplete.")

        for record in upgraded_records:
            backup_path = record["backup_path"]
            if os.path.exists(backup_path):
                try:
                    os.remove(backup_path)
                except Exception:
                    pass

        input(t("press_enter"))
        return

    section("UPGRADE SUCCESS")
    write_log(log_file, "Health check passed. Upgrade successful.")
    cprint(Color.GREEN, "✅ Upgrade successful!")

    for record in upgraded_records:
        backup_path = record["backup_path"]
        if os.path.exists(backup_path):
            try:
                os.remove(backup_path)
                write_log(log_file, f"Removed backup {backup_path}")
            except Exception:
                pass

    if input_yes_no_text(
        "Do you want to clear the UPGRADE_TMP directory (keep the directory itself)?",
        default=True
    ):
        cleanup_upgrade_tmp(upgrade_dir, log_file)
    else:
        cprint(Color.YELLOW, "UPGRADE_TMP directory kept as is.")

    if input_yes_no_text("Do you want to restart the program now?", default=True):
        cprint(Color.BLUE, "Restarting...")
        short_pause()
        try:
            os.execv(sys.executable, [sys.executable] + sys.argv)
        except Exception as e:
            cprint(Color.RED, f"Restart failed: {e}")
            cprint(Color.YELLOW, "Please restart manually.")
    else:
        cprint(Color.YELLOW, "You can restart later.")

    input(t("press_enter"))


def system_upgrade_menu():
    """
    Standard zero-argument menu entry for tools/system_tools.py.
    """
    program_upgrade()
