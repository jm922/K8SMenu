#!/usr/bin/env python3
"""
YAML file management tools
"""

import os
import glob
from datetime import datetime
from utils.color import cprint, Color
from utils.lang import t
from utils.helpers import input_yes_no_text

def get_yaml_files():
    yaml_files = glob.glob("*.yaml") + glob.glob("*.yml")
    yaml_files.sort()
    return yaml_files

def list_yaml_files():
    yaml_files = get_yaml_files()
    if not yaml_files:
        cprint(Color.YELLOW, t("yaml_no_files"))
        return [], {}
    print(f"\n{Color.BOLD}{Color.CYAN}YAML Files in current directory:{Color.END}")
    print("-" * 60)
    file_map = {}
    for idx, filename in enumerate(yaml_files, 1):
        file_size = os.path.getsize(filename)
        mod_time = datetime.fromtimestamp(os.path.getmtime(filename)).strftime("%Y-%m-%d %H:%M")
        print(f"{Color.GREEN}{idx:<4}{Color.END} {filename:<35} {file_size:>8} bytes  {mod_time}")
        file_map[str(idx)] = filename
        file_map[filename] = filename
    return yaml_files, file_map

def view_yaml_file(filename):
    print("\n" + t("yaml_view_title"))
    print("=" * 60)
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            content = f.read()
            print(content)
    except Exception as e:
        cprint(Color.RED, f"Failed to read file: {e}")
    print("=" * 60)
    input(t("press_enter"))

def yaml_file_management():
    while True:
        print("\n" + t("yaml_management_title"))
        yaml_files, file_map = list_yaml_files()
        if not yaml_files:
            input(t("press_enter"))
            return
        print("\nOptions:")
        print("  • Enter numbers separated by space to delete (e.g., '1 3 5')")
        print("  • Enter 'v' followed by number to view file (e.g., 'v 1')")
        print("  • Enter 'q' or 'quit' to exit")
        print("  • Enter 'menu' to return to main menu")
        choice = input("\nSelect option: ").strip().lower()
        if choice in ['q', 'quit']:
            return
        if choice in ['menu', 'back']:
            return
        if choice.startswith('v '):
            view_num = choice[2:].strip()
            if view_num in file_map:
                view_yaml_file(file_map[view_num])
                continue
            else:
                cprint(Color.RED, f"Invalid file number: {view_num}")
                continue
        # Handle delete
        if ' ' in choice:
            parts = choice.split()
            files_to_delete = []
            invalid = []
            for part in parts:
                if part in file_map:
                    files_to_delete.append(file_map[part])
                else:
                    invalid.append(part)
            if invalid:
                cprint(Color.RED, f"Invalid selections: {', '.join(invalid)}")
            if not files_to_delete:
                continue
            print("\nSelected files to delete:")
            for fname in files_to_delete:
                print(f"  • {fname}")
            if len(files_to_delete) == 1:
                confirm_msg = t("yaml_delete_confirm_single", name=files_to_delete[0])
            else:
                confirm_msg = t("yaml_delete_confirm_multiple", count=len(files_to_delete))
            if input_yes_no_text(confirm_msg, default=False):
                success = 0
                fail = 0
                for fname in files_to_delete:
                    try:
                        os.remove(fname)
                        cprint(Color.GREEN, t("yaml_delete_success", name=fname))
                        success += 1
                    except Exception as e:
                        cprint(Color.RED, t("yaml_delete_fail", name=fname, error=e))
                        fail += 1
                print(f"\n{Color.BOLD}{t('yaml_delete_summary')}{Color.END}")
                cprint(Color.GREEN, f"  ✅ Successfully deleted: {success}")
                if fail > 0:
                    cprint(Color.RED, f"  ❌ Failed to delete: {fail}")
            else:
                cprint(Color.YELLOW, "Deletion cancelled.")
        else:
            if choice in file_map:
                files_to_delete = [file_map[choice]]
                print("\nSelected file to delete:")
                print(f"  • {files_to_delete[0]}")
                if input_yes_no_text(t("yaml_delete_confirm_single", name=files_to_delete[0]), default=False):
                    try:
                        os.remove(files_to_delete[0])
                        cprint(Color.GREEN, t("yaml_delete_success", name=files_to_delete[0]))
                    except Exception as e:
                        cprint(Color.RED, t("yaml_delete_fail", name=files_to_delete[0], error=e))
                else:
                    cprint(Color.YELLOW, "Deletion cancelled.")
            else:
                cprint(Color.RED, t("yaml_invalid"))
