#!/usr/bin/env python3
"""
Program upgrade tool - upgrades .py files from UPGRADE_TMP directory
with automatic rollback and post-upgrade health check.
Supports flat UPGRADE_TMP directory: finds target files by name recursively.
"""

import os
import sys
import time
import shutil
import subprocess
from datetime import datetime
from utils.color import cprint, Color
from utils.lang import t
from utils.helpers import input_yes_no_text

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
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(log_line + "\n")
    if level == "ERROR":
        cprint(Color.RED, message)
    elif level == "WARNING":
        cprint(Color.YELLOW, message)
    else:
        cprint(Color.BLUE, message)

def find_target_file(base_dir, filename, exclude_dir):
    """
    Recursively search for a file with given filename in base_dir,
    excluding the exclude_dir (UPGRADE_TMP) and its contents.
    Returns list of found paths (may have multiple matches).
    """
    matches = []
    exclude_abs = os.path.abspath(exclude_dir)
    for root, dirs, files in os.walk(base_dir):
        if os.path.abspath(root) == exclude_abs:
            continue
        if filename in files:
            matches.append(os.path.join(root, filename))
    return matches

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
    for dest_path, backup_path in upgraded_records:
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

def test_new_program(base_dir, log_file):
    """
    Test if the upgraded program can start properly.
    Returns (True, None) if successful, (False, error_message) otherwise.
    """
    write_log(log_file, "Performing post-upgrade health check...")
    cprint(Color.BLUE, "Testing new program integrity...")
    time.sleep(5)
    test_cmd = [sys.executable, '-c',
                "import sys; sys.path.insert(0, '.'); "
                "from version import VERSION; "
                "from utils.color import Color; "
                "print('Health check passed')"]
    try:
        result = subprocess.run(test_cmd, capture_output=True, text=True, timeout=30, cwd=base_dir)
        if result.returncode == 0:
            write_log(log_file, "Health check succeeded.")
            cprint(Color.GREEN, "✅ New program is healthy.")
            return True, None
        else:
            error_msg = result.stderr.strip()
            write_log(log_file, f"Health check failed: {error_msg}", "ERROR")
            return False, error_msg
    except Exception as e:
        error_msg = str(e)
        write_log(log_file, f"Health check exception: {error_msg}", "ERROR")
        return False, error_msg

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
    
    py_files = []
    for file in os.listdir(upgrade_dir):
        if file.endswith('.py'):
            full_path = os.path.join(upgrade_dir, file)
            py_files.append((full_path, file))
    
    if not py_files:
        write_log(log_file, "No .py files found in UPGRADE_TMP.", "WARNING")
        cprint(Color.YELLOW, "No .py files found in UPGRADE_TMP.")
        input(t("press_enter"))
        return
    
    total = len(py_files)
    write_log(log_file, f"Found {total} .py file(s) to process.")
    cprint(Color.CYAN, f"Found {total} .py file(s) to upgrade.")
    time.sleep(5)
    
    success_count = 0
    fail_count = 0
    skip_count = 0
    upgraded_records = []
    
    for idx, (src_full, filename) in enumerate(py_files, 1):
        print(f"\n[{idx}/{total}] Processing: {filename}")
        time.sleep(2)
        
        matches = find_target_file(base_dir, filename, upgrade_dir)
        if not matches:
            write_log(log_file, f"Skipping {filename}: target file not found.", "WARNING")
            cprint(Color.YELLOW, f"  ⚠️ Target file not found, skipping.")
            skip_count += 1
            time.sleep(2)
            continue
        elif len(matches) > 1:
            write_log(log_file, f"Multiple matches for {filename}: {matches}", "WARNING")
            cprint(Color.YELLOW, f"  ⚠️ Multiple target files found, skipping.")
            skip_count += 1
            time.sleep(2)
            continue
        
        dest_path = matches[0]
        backup_success, backup_path = backup_file(dest_path, log_file)
        if not backup_success:
            cprint(Color.RED, f"  ❌ Backup failed, skipping.")
            fail_count += 1
            time.sleep(2)
            continue
        time.sleep(2)
        
        try:
            orig_stat = os.stat(dest_path)
            orig_mode = orig_stat.st_mode
            write_log(log_file, f"Original permissions: {oct(orig_mode)}")
        except:
            orig_mode = None
        
        try:
            shutil.copy2(src_full, dest_path)
            write_log(log_file, f"Copied {src_full} -> {dest_path}")
        except Exception as e:
            write_log(log_file, f"Copy failed: {e}", "ERROR")
            restore_backup(dest_path, log_file)
            fail_count += 1
            time.sleep(2)
            continue
        time.sleep(2)
        
        if orig_mode is not None:
            try:
                os.chmod(dest_path, orig_mode)
                write_log(log_file, f"Restored permissions to {oct(orig_mode)}")
            except Exception as e:
                write_log(log_file, f"Failed to restore permissions: {e}", "WARNING")
                cprint(Color.YELLOW, f"  ⚠️ Could not restore permissions")
        else:
            os.chmod(dest_path, 0o644)
            write_log(log_file, "Set default permissions (644)")
        
        upgraded_records.append((dest_path, backup_path))
        success_count += 1
        cprint(Color.GREEN, f"  ✅ Successfully upgraded {filename}")
        time.sleep(2)
    
    print("\n" + "="*40)
    cprint(Color.BOLD, "Upgrade Copy Summary:")
    cprint(Color.GREEN, f"  ✅ Successfully copied: {success_count}")
    if fail_count > 0:
        cprint(Color.RED, f"  ❌ Failed: {fail_count}")
    if skip_count > 0:
        cprint(Color.YELLOW, f"  ⏭️ Skipped: {skip_count}")
    print("="*40)
    time.sleep(5)
    
    if success_count == 0:
        write_log(log_file, "No files upgraded. Aborting.", "ERROR")
        cprint(Color.RED, "No files upgraded. Upgrade aborted.")
        input(t("press_enter"))
        return
    
    write_log(log_file, "Starting post-upgrade health check...")
    cprint(Color.BLUE, "\nPerforming health check on new program...")
    healthy, error_msg = test_new_program(base_dir, log_file)
    
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
        for _, backup_path in upgraded_records:
            if os.path.exists(backup_path):
                try:
                    os.remove(backup_path)
                except:
                    pass
        input(t("press_enter"))
        return
    
    write_log(log_file, "Health check passed. Upgrade successful.")
    cprint(Color.GREEN, "\n✅ Upgrade successful!")
    
    for _, backup_path in upgraded_records:
        if os.path.exists(backup_path):
            try:
                os.remove(backup_path)
                write_log(log_file, f"Removed backup {backup_path}")
            except:
                pass
    
    # 询问是否清空 UPGRADE_TMP 目录（保留目录本身）
    if input_yes_no_text("Do you want to clear the UPGRADE_TMP directory (keep the directory itself)?", default=True):
        try:
            # 遍历删除目录内所有文件和子目录
            for item in os.listdir(upgrade_dir):
                item_path = os.path.join(upgrade_dir, item)
                if os.path.isfile(item_path) or os.path.islink(item_path):
                    os.unlink(item_path)
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)
            write_log(log_file, f"Cleared contents of UPGRADE_TMP directory: {upgrade_dir}")
            cprint(Color.GREEN, "✅ UPGRADE_TMP directory cleared (directory kept).")
        except Exception as e:
            write_log(log_file, f"Failed to clear UPGRADE_TMP directory: {e}", "WARNING")
            cprint(Color.YELLOW, f"⚠️ Could not clear UPGRADE_TMP directory: {e}")
    else:
        cprint(Color.YELLOW, "UPGRADE_TMP directory kept as is.")
    
    if input_yes_no_text("\nDo you want to restart the program now?", default=True):
        cprint(Color.BLUE, "Restarting...")
        time.sleep(2)
        try:
            os.execv(sys.executable, [sys.executable] + sys.argv)
        except Exception as e:
            cprint(Color.RED, f"Restart failed: {e}")
            cprint(Color.YELLOW, "Please restart manually.")
    else:
        cprint(Color.YELLOW, "You can restart later.")
    
    input(t("press_enter"))
