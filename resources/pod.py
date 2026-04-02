#!/usr/bin/env python3
"""
Pod management functions - with Restarts column (current namespace only)
"""

import subprocess
import os
from datetime import datetime
from utils.color import cprint, Color
from utils.lang import t
from utils.helpers import (input_required, input_with_default, input_yes_no,
                           input_yes_no_text, apply_yaml, delete_resource)
from utils.yaml_helpers import (check_and_install_vim, edit_yaml_with_vim,
                                validate_yaml_syntax, validate_with_kubectl, apply_yaml_file)
from resources.common import get_pod_list_with_numbers, resolve_pod_identifier

def list_pods_with_numbers():
    """Display numbered Pod list with Restarts column (current namespace only)"""
    print("\n" + t("list_pods_title"))
    result = subprocess.run(['kubectl', 'get', 'pods', '-o', 'wide', '--show-labels'], capture_output=True, text=True)
    if result.returncode != 0:
        cprint(Color.RED, t("fail") + " " + t("list_pods_fail") + ": " + result.stderr)
        return
    
    lines = result.stdout.strip().split('\n')
    if len(lines) <= 1:
        cprint(Color.YELLOW, t("list_pods_no_pods"))
        return
    
    pod_data = []
    for line in lines[1:]:
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) >= 7:
            name = parts[0]
            ready = parts[1]
            status = parts[2]
            restarts = parts[3]
            age = parts[4]
            ip = parts[5]
            node = parts[6]
            labels = parts[-1] if len(parts) > 7 else ''
            pod_data.append({
                'name': name,
                'ready': ready,
                'status': status,
                'restarts': restarts,
                'age': age,
                'ip': ip,
                'node': node,
                'labels': labels
            })
    
    print(f"{Color.BOLD}{Color.CYAN}{'#':<4} {'Pod Name':<30} {'Ready':<8} {'Restarts':<10} {'Status':<12} {'IP':<16} {'Node':<20} {'Labels':<30}{Color.END}")
    print("-" * 135)
    for idx, data in enumerate(pod_data, 1):
        labels = data['labels']
        if len(labels) > 30:
            labels = labels[:27] + '...'
        print(f"{Color.GREEN}{idx:<4}{Color.END} {data['name']:<30} {data['ready']:<8} {data['restarts']:<10} {data['status']:<12} {data['ip']:<16} {data['node']:<20} {labels:<30}")
    
    return pod_data

def quick_deploy():
    print("\n" + t("create_pod_title"))
    name = input_required("create_pod_name")
    image = input_required("create_pod_image")
    port = input_with_default("create_pod_port", "80")
    env_vars = []
    while input_yes_no("create_pod_env_ask", False):
        key = input_required("create_pod_env_key")
        value = input_required("create_pod_env_value")
        env_vars.append({"name": key, "value": value})
    yaml_content = f"""apiVersion: v1
kind: Pod
metadata:
  name: {name}
spec:
  containers:
  - name: {name}
    image: {image}
    ports:
    - containerPort: {port}
"""
    if env_vars:
        env_yaml = "    env:\n"
        for e in env_vars:
            env_yaml += f"    - name: {e['name']}\n      value: {e['value']}\n"
        yaml_content += env_yaml
    apply_yaml(yaml_content)

def generate_pod_template():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"pod_{timestamp}.yaml"
    template = """# Kubernetes Pod YAML Template
# Edit this file to create your Pod

apiVersion: v1
kind: Pod
metadata:
  name: my-pod
  labels:
    app: my-app
spec:
  containers:
  - name: my-container
    image: nginx:latest
    ports:
    - containerPort: 80
    # env:
    # - name: ENV_VAR_NAME
    #   value: "value"
"""
    return filename, template

def pod_yaml_editor_mode():
    print("\n" + t("yaml_editor_title"))
    filename, template = generate_pod_template()
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(template)
    cprint(Color.GREEN, t("yaml_file_created", file=filename))
    if not check_and_install_vim():
        cprint(Color.RED, "Cannot proceed without vim editor.")
        return
    backup_file = filename + ".backup"
    os.rename(filename, backup_file)
    cprint(Color.BLUE, t("yaml_editor_backup", backup=backup_file))
    if not edit_yaml_with_vim(backup_file):
        cprint(Color.RED, "Failed to edit YAML file.")
        os.rename(backup_file, filename)
        return
    while True:
        valid, _, _ = validate_yaml_syntax(backup_file)
        if not valid:
            if not input_yes_no("yaml_validate_retry", default=True):
                cprint(Color.YELLOW, t("yaml_editor_aborted"))
                os.rename(backup_file, filename)
                return
            edit_yaml_with_vim(backup_file)
            continue
        kubectl_valid, _ = validate_with_kubectl(backup_file)
        if not kubectl_valid:
            if not input_yes_no("yaml_validate_retry", default=True):
                cprint(Color.YELLOW, t("yaml_editor_aborted"))
                os.rename(backup_file, filename)
                return
            edit_yaml_with_vim(backup_file)
            continue
        break
    if apply_yaml_file(backup_file):
        os.rename(backup_file, filename)
        cprint(Color.GREEN, t("yaml_file_saved", file=filename))
    else:
        os.rename(backup_file, filename)
        cprint(Color.YELLOW, f"YAML file kept for reference: {filename}")

def delete_pod():
    while True:
        print("\n" + t("delete_pod_title"))
        numbered_list, pod_map, _ = get_pod_list_with_numbers()
        if numbered_list is None or not numbered_list:
            cprint(Color.YELLOW, t("delete_pod_no_pods"))
            return
        print(f"\n{Color.BOLD}{Color.CYAN}Currently running Pods:{Color.END}")
        for idx, name, data in numbered_list:
            print(f"  {Color.GREEN}{idx}{Color.END}. {name} ({data['status']})")
        print("\n" + t("delete_pod_hint"))
        identifier = input(f"\n{t('delete_pod_name')}: ").strip().lower()
        if identifier in ['q', 'quit']:
            cprint(Color.YELLOW, t("delete_exiting"))
            return
        if identifier in ['menu', 'back']:
            cprint(Color.YELLOW, t("delete_returning"))
            return
        if not identifier:
            cprint(Color.YELLOW, t("delete_no_input"))
            return
        pods_to_delete = []
        if ' ' in identifier:
            parts = identifier.split()
            for part in parts:
                if part in pod_map:
                    pods_to_delete.append(pod_map[part])
                elif part.isdigit():
                    cprint(Color.RED, t("delete_pod_not_found", num=part))
                else:
                    cprint(Color.RED, t("delete_pod_invalid"))
        else:
            pod_name = resolve_pod_identifier(identifier, pod_map)
            if pod_name:
                pods_to_delete.append(pod_name)
            else:
                if identifier.isdigit():
                    cprint(Color.RED, t("delete_pod_not_found", num=identifier))
                else:
                    cprint(Color.RED, t("delete_pod_invalid"))
                continue
        if not pods_to_delete:
            cprint(Color.YELLOW, t("delete_no_valid"))
            continue
        print(f"\n{Color.YELLOW}Selected Pods to delete:{Color.END}")
        for p in pods_to_delete:
            print(f"  • {p}")
        if len(pods_to_delete) == 1:
            confirm_msg = t("delete_pod_confirm_single", name=pods_to_delete[0])
        else:
            confirm_msg = t("delete_pod_confirm_multiple", count=len(pods_to_delete))
        if input_yes_no_text(confirm_msg, default=False):
            success = 0
            fail = 0
            for p in pods_to_delete:
                result = subprocess.run(['kubectl', 'delete', 'pod', p], capture_output=True, text=True)
                if result.returncode == 0:
                    cprint(Color.GREEN, t("delete_pod_success", name=p))
                    success += 1
                else:
                    cprint(Color.RED, t("delete_pod_fail", name=p, error=result.stderr.strip()))
                    fail += 1
            print(f"\n{Color.BOLD}{t('delete_pod_summary')}{Color.END}")
            cprint(Color.GREEN, f"  ✅ Successfully deleted: {success}")
            if fail > 0:
                cprint(Color.RED, f"  ❌ Failed to delete: {fail}")
            if not input_yes_no_text(t("delete_more_prompt"), default=False):
                return
        else:
            cprint(Color.YELLOW, t("delete_cancelled"))
            if not input_yes_no_text(t("delete_try_again"), default=True):
                return

def list_pods():
    list_pods_with_numbers()
    input("\nPress Enter to continue...")

def describe_pod():
    print("\n" + t("describe_pod_title"))
    numbered_list, pod_map, _ = get_pod_list_with_numbers()
    if numbered_list is None or not numbered_list:
        cprint(Color.YELLOW, "No running Pods available.")
        input(t("press_enter"))
        return
    print(f"\n{Color.BOLD}{Color.CYAN}Currently running Pods:{Color.END}")
    for idx, name, data in numbered_list:
        print(f"  {Color.GREEN}{idx}{Color.END}. {name} ({data['status']})")
    print("\n" + t("describe_pod_hint"))
    identifier = input_required("describe_pod_name")
    pod_name = resolve_pod_identifier(identifier, pod_map)
    if not pod_name:
        if identifier.isdigit():
            cprint(Color.RED, t("delete_pod_not_found", num=identifier))
        else:
            cprint(Color.RED, t("delete_pod_invalid"))
        input(t("press_enter"))
        return
    cprint(Color.BLUE, t("describe_pod_fetch", name=pod_name))
    result = subprocess.run(['kubectl', 'describe', 'pod', pod_name], capture_output=True, text=True)
    if result.returncode == 0:
        print(result.stdout)
    else:
        cprint(Color.RED, t("fail") + " " + t("describe_pod_fail") + ": " + result.stderr)
    input(t("press_enter"))

def create_pod_menu():
    while True:
        print("\n" + t("create_pod_submenu_title"))
        print(t("create_pod_submenu_1"))
        print(t("create_pod_submenu_2"))
        print(t("create_pod_submenu_3"))
        choice = input(t("create_pod_submenu_prompt")).strip()
        if choice == '1':
            quick_deploy()
        elif choice == '2':
            pod_yaml_editor_mode()
        elif choice == '3':
            break
        else:
            cprint(Color.RED, t("invalid_option"))

def pod_menu():
    while True:
        print("\n" + t("pod_menu_title"))
        print(t("pod_menu_1"))
        print(t("pod_menu_2"))
        print(t("pod_menu_3"))
        print(t("pod_menu_4"))
        print(t("pod_menu_5"))
        choice = input(t("pod_menu_prompt")).strip()
        if choice == '1':
            create_pod_menu()
        elif choice == '2':
            delete_pod()
        elif choice == '3':
            list_pods()
        elif choice == '4':
            describe_pod()
        elif choice == '5':
            break
        else:
            cprint(Color.RED, t("invalid_option"))
