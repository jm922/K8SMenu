#!/usr/bin/env python3
"""
Deployment management functions - with labels column in list
"""

import subprocess
import os
import json
from datetime import datetime
from utils.color import cprint, Color
from utils.lang import t
from utils.helpers import (input_required, input_with_default, input_yes_no,
                           input_yes_no_text, apply_yaml)
from utils.yaml_helpers import (check_and_install_vim, edit_yaml_with_vim,
                                validate_yaml_syntax, validate_with_kubectl, apply_yaml_file)
from resources.common import (get_deployment_list_with_numbers, resolve_deployment_identifier,
                              get_deployment_replicaset_pod_info)

def list_deployments_with_numbers():
    """Display numbered list of Deployments with Labels column"""
    print("\n" + t("list_deployments_title"))
    # Use -o wide for basic info
    result = subprocess.run(['kubectl', 'get', 'deployments', '-o', 'wide'], capture_output=True, text=True)
    if result.returncode != 0:
        cprint(Color.RED, t("fail") + " " + t("list_deployments_fail") + ": " + result.stderr)
        return None
    
    # Get labels via JSON
    json_result = subprocess.run(['kubectl', 'get', 'deployments', '-o', 'json'], capture_output=True, text=True)
    labels_map = {}
    if json_result.returncode == 0:
        try:
            data = json.loads(json_result.stdout)
            for item in data.get('items', []):
                name = item['metadata']['name']
                labels = item['metadata'].get('labels', {})
                labels_str = ','.join([f"{k}={v}" for k, v in labels.items()])
                labels_map[name] = labels_str
        except:
            pass
    
    lines = result.stdout.strip().split('\n')
    if len(lines) <= 1:
        cprint(Color.YELLOW, t("list_deployments_no_deployments"))
        return None
    
    dep_data = []
    for line in lines[1:]:
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) >= 5:
            name = parts[0]
            ready = parts[1] if len(parts) > 1 else ''
            up_to_date = parts[2] if len(parts) > 2 else ''
            available = parts[3] if len(parts) > 3 else ''
            age = parts[4] if len(parts) > 4 else ''
            images = parts[6] if len(parts) > 6 else ''
            labels = labels_map.get(name, '')
            dep_data.append({
                'name': name,
                'ready': ready,
                'up_to_date': up_to_date,
                'available': available,
                'age': age,
                'images': images,
                'labels': labels
            })
    
    print(f"{Color.BOLD}{Color.CYAN}{'#':<4} {'Name':<30} {'Ready':<8} {'Up-to-date':<10} {'Available':<10} {'Age':<8} {'Image':<40} {'Labels':<30}{Color.END}")
    print("-" * 150)
    for idx, data in enumerate(dep_data, 1):
        image = data['images']
        if len(image) > 40:
            image = image[:37] + '...'
        labels = data['labels']
        if len(labels) > 30:
            labels = labels[:27] + '...'
        print(f"{Color.GREEN}{idx:<4}{Color.END} {data['name']:<30} {data['ready']:<8} {data['up_to_date']:<10} {data['available']:<10} {data['age']:<8} {image:<40} {labels:<30}")
    
    numbered_list = [(idx, d['name'], d) for idx, d in enumerate(dep_data, 1)]
    dep_map = {str(idx): d['name'] for idx, d in enumerate(dep_data, 1)}
    dep_map.update({d['name']: d['name'] for d in dep_data})
    return numbered_list, dep_map

def show_deployment_pods(dep_name=None):
    """Show Pods belonging to a specific Deployment (current namespace, with Restarts column)"""
    if dep_name is None:
        print("\n" + t("show_deployment_pods_title"))
        result = list_deployments_with_numbers()
        if result is None:
            return
        numbered_list, dep_map = result
        if not numbered_list:
            cprint(Color.YELLOW, t("list_deployments_no_deployments"))
            input(t("press_enter"))
            return
        
        print(f"\n{Color.BOLD}{Color.CYAN}Available Deployments:{Color.END}")
        for idx, name, data in numbered_list:
            print(f"  {Color.GREEN}{idx}{Color.END}. {name} (Ready: {data['ready']})")
        
        identifier = input_required("describe_deployment_name")
        dep_name = resolve_deployment_identifier(identifier, dep_map)
        if not dep_name:
            cprint(Color.RED, t("export_not_found", name=identifier))
            input(t("press_enter"))
            return
    
    # Get deployment's selector labels
    result = subprocess.run(['kubectl', 'get', 'deployment', dep_name, '-o', 'json'], capture_output=True, text=True)
    if result.returncode != 0:
        cprint(Color.RED, t("show_deployment_pods_fail", error=result.stderr))
        input(t("press_enter"))
        return
    
    try:
        dep_json = json.loads(result.stdout)
        selector = dep_json.get('spec', {}).get('selector', {}).get('matchLabels', {})
        if not selector:
            selector = {'app': dep_name}
        label_selector = ','.join([f"{k}={v}" for k, v in selector.items()])
    except:
        label_selector = f"app={dep_name}"
    
    cmd = ['kubectl', 'get', 'pods', '-l', label_selector, '-o', 'wide', '--show-labels']
    pod_result = subprocess.run(cmd, capture_output=True, text=True)
    if pod_result.returncode != 0:
        cprint(Color.RED, t("show_deployment_pods_fail", error=pod_result.stderr))
        input(t("press_enter"))
        return
    
    print(f"\n{Color.BOLD}{Color.CYAN}Pods for Deployment '{dep_name}' (selector: {label_selector}):{Color.END}")
    lines = pod_result.stdout.strip().split('\n')
    if len(lines) <= 1:
        cprint(Color.YELLOW, "No pods found.")
    else:
        print(f"{Color.BOLD}{Color.CYAN}{'Pod Name':<30} {'Ready':<8} {'Restarts':<10} {'Status':<12} {'IP':<16} {'Node':<20} {'Labels':<30}{Color.END}")
        print("-" * 135)
        for line in lines[1:]:
            if not line.strip():
                continue
            parts = line.split()
            if len(parts) >= 8:
                name = parts[0]
                ready = parts[1]
                status = parts[2]
                restarts = parts[3]
                ip = parts[5] if len(parts) > 5 else ''
                node = parts[6] if len(parts) > 6 else ''
                labels = parts[-1] if len(parts) > 7 else ''
                if len(labels) > 30:
                    labels = labels[:27] + '...'
                print(f"{name:<30} {ready:<8} {restarts:<10} {status:<12} {ip:<16} {node:<20} {labels:<30}")
    input(t("press_enter"))

def list_deployments():
    """List all Deployments, then optionally show Pods of a selected Deployment"""
    result = list_deployments_with_numbers()
    if result is None:
        return
    numbered_list, dep_map = result
    if not numbered_list:
        return
    
    if input_yes_no_text(t("list_deployments_ask_show_pods"), default=False):
        print(t("list_deployments_select_pods"))
        identifier = input("").strip().lower()
        if identifier in ['q', 'quit']:
            return
        dep_name = resolve_deployment_identifier(identifier, dep_map)
        if dep_name:
            show_deployment_pods(dep_name)
        else:
            cprint(Color.RED, t("export_not_found", name=identifier))
    input("\nPress Enter to continue...")

# ---------- The following functions are unchanged from the previous version ----------
def quick_deploy_deployment():
    print("\n" + t("create_deployment_title"))
    name = input_required("create_deployment_name")
    image = input_required("create_deployment_image")
    replicas = input_with_default("create_deployment_replicas", "1")
    port = input_with_default("create_deployment_port", "80")
    env_vars = []
    while input_yes_no("create_deployment_env_ask", False):
        key = input_required("create_deployment_env_key")
        value = input_required("create_deployment_env_value")
        env_vars.append({"name": key, "value": value})
    yaml_content = f"""apiVersion: apps/v1
kind: Deployment
metadata:
  name: {name}
  labels:
    app: {name}
spec:
  replicas: {replicas}
  selector:
    matchLabels:
      app: {name}
  template:
    metadata:
      labels:
        app: {name}
    spec:
      containers:
      - name: {name}
        image: {image}
        ports:
        - containerPort: {port}
"""
    if env_vars:
        env_yaml = "        env:\n"
        for e in env_vars:
            env_yaml += f"        - name: {e['name']}\n          value: {e['value']}\n"
        yaml_content = yaml_content.replace("ports:\n        - containerPort: {port}\n", f"ports:\n        - containerPort: {port}\n{env_yaml}")
    apply_yaml(yaml_content)

def generate_deployment_template():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"deployment_{timestamp}.yaml"
    template = """# Kubernetes Deployment YAML Template
# Edit this file to create your Deployment

apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-deployment
  labels:
    app: my-app
spec:
  replicas: 3
  selector:
    matchLabels:
      app: my-app
  template:
    metadata:
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

def deployment_yaml_editor_mode():
    print("\n" + t("deployment_yaml_editor_title"))
    filename, template = generate_deployment_template()
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(template)
    cprint(Color.GREEN, t("deployment_yaml_file_created", file=filename))
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
                cprint(Color.YELLOW, t("deployment_yaml_editor_aborted"))
                os.rename(backup_file, filename)
                return
            edit_yaml_with_vim(backup_file)
            continue
        kubectl_valid, _ = validate_with_kubectl(backup_file)
        if not kubectl_valid:
            if not input_yes_no("yaml_validate_retry", default=True):
                cprint(Color.YELLOW, t("deployment_yaml_editor_aborted"))
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

def delete_deployment():
    while True:
        print("\n" + t("delete_deployment_title"))
        numbered_list, dep_map, _ = get_deployment_list_with_numbers()
        if numbered_list is None or not numbered_list:
            cprint(Color.YELLOW, t("delete_deployment_no_pods"))
            return
        print(f"\n{Color.BOLD}{Color.CYAN}Current Deployments:{Color.END}")
        for idx, name, data in numbered_list:
            print(f"  {Color.GREEN}{idx}{Color.END}. {name} (Ready: {data['ready']}, Available: {data['available']})")
        print("\n" + t("delete_deployment_hint"))
        identifier = input(f"\n{t('delete_deployment_name')}: ").strip().lower()
        if identifier in ['q', 'quit']:
            cprint(Color.YELLOW, t("delete_exiting"))
            return
        if identifier in ['menu', 'back']:
            cprint(Color.YELLOW, t("delete_returning"))
            return
        if not identifier:
            cprint(Color.YELLOW, t("delete_no_input"))
            return
        deps_to_delete = []
        if ' ' in identifier:
            parts = identifier.split()
            for part in parts:
                if part in dep_map:
                    deps_to_delete.append(dep_map[part])
                elif part.isdigit():
                    cprint(Color.RED, t("delete_deployment_not_found", num=part))
                else:
                    cprint(Color.RED, t("delete_deployment_invalid"))
        else:
            dep_name = resolve_deployment_identifier(identifier, dep_map)
            if dep_name:
                deps_to_delete.append(dep_name)
            else:
                if identifier.isdigit():
                    cprint(Color.RED, t("delete_deployment_not_found", num=identifier))
                else:
                    cprint(Color.RED, t("delete_deployment_invalid"))
                continue
        if not deps_to_delete:
            cprint(Color.YELLOW, t("delete_no_valid"))
            continue
        print(f"\n{Color.YELLOW}Selected Deployments to delete:{Color.END}")
        for d in deps_to_delete:
            print(f"  • {d}")
        if len(deps_to_delete) == 1:
            confirm_msg = t("delete_deployment_confirm_single", name=deps_to_delete[0])
        else:
            confirm_msg = t("delete_deployment_confirm_multiple", count=len(deps_to_delete))
        if input_yes_no_text(confirm_msg, default=False):
            success = 0
            fail = 0
            for d in deps_to_delete:
                result = subprocess.run(['kubectl', 'delete', 'deployment', d], capture_output=True, text=True)
                if result.returncode == 0:
                    cprint(Color.GREEN, t("delete_deployment_success", name=d))
                    success += 1
                else:
                    cprint(Color.RED, t("delete_deployment_fail", name=d, error=result.stderr.strip()))
                    fail += 1
            print(f"\n{Color.BOLD}{t('delete_deployment_summary')}{Color.END}")
            cprint(Color.GREEN, f"  ✅ Successfully deleted: {success}")
            if fail > 0:
                cprint(Color.RED, f"  ❌ Failed to delete: {fail}")
            if not input_yes_no_text(t("delete_more_prompt"), default=False):
                return
        else:
            cprint(Color.YELLOW, t("delete_cancelled"))
            if not input_yes_no_text(t("delete_try_again"), default=True):
                return

def describe_deployment():
    print("\n" + t("describe_deployment_title"))
    numbered_list, dep_map, _ = get_deployment_list_with_numbers()
    if numbered_list is None or not numbered_list:
        cprint(Color.YELLOW, "No Deployments available.")
        input(t("press_enter"))
        return
    print(f"\n{Color.BOLD}{Color.CYAN}Current Deployments:{Color.END}")
    for idx, name, data in numbered_list:
        print(f"  {Color.GREEN}{idx}{Color.END}. {name} (Ready: {data['ready']})")
    print("\n" + t("describe_deployment_hint"))
    identifier = input_required("describe_deployment_name")
    dep_name = resolve_deployment_identifier(identifier, dep_map)
    if not dep_name:
        if identifier.isdigit():
            cprint(Color.RED, t("delete_deployment_not_found", num=identifier))
        else:
            cprint(Color.RED, t("delete_deployment_invalid"))
        input(t("press_enter"))
        return
    cprint(Color.BLUE, t("describe_deployment_fetch", name=dep_name))
    result = subprocess.run(['kubectl', 'describe', 'deployment', dep_name], capture_output=True, text=True)
    if result.returncode == 0:
        print(result.stdout)
    else:
        cprint(Color.RED, t("fail") + " " + t("describe_deployment_fail") + ": " + result.stderr)
    input(t("press_enter"))

# ---------- Export Deployment Functions ----------
def show_deployment_yaml():
    numbered_list, dep_map, _ = get_deployment_list_with_numbers()
    if numbered_list is None or not numbered_list:
        cprint(Color.YELLOW, t("list_deployments_no_deployments"))
        return
    print(f"\n{Color.BOLD}{Color.CYAN}Available Deployments:{Color.END}")
    for idx, name, data in numbered_list:
        print(f"  {Color.GREEN}{idx}{Color.END}. {name} (Ready: {data['ready']})")
    identifier = input(f"\n{t('export_select_deployment')}").strip()
    dep_name = resolve_deployment_identifier(identifier, dep_map)
    if not dep_name:
        cprint(Color.RED, t("export_not_found", name=identifier))
        input(t("press_enter"))
        return
    cprint(Color.BLUE, t("export_fetching", name=dep_name))
    result = subprocess.run(['kubectl', 'get', 'deployment', dep_name, '-o', 'yaml'],
                            capture_output=True, text=True)
    if result.returncode != 0:
        cprint(Color.RED, t("export_fail", error=result.stderr))
    else:
        print("\n" + t("export_display_title", name=dep_name))
        print(result.stdout)
    input(t("press_enter"))

def save_deployment_yaml():
    numbered_list, dep_map, _ = get_deployment_list_with_numbers()
    if numbered_list is None or not numbered_list:
        cprint(Color.YELLOW, t("list_deployments_no_deployments"))
        return
    print(f"\n{Color.BOLD}{Color.CYAN}Available Deployments:{Color.END}")
    for idx, name, data in numbered_list:
        print(f"  {Color.GREEN}{idx}{Color.END}. {name} (Ready: {data['ready']})")
    identifier = input(f"\n{t('export_select_deployment')}").strip()
    dep_name = resolve_deployment_identifier(identifier, dep_map)
    if not dep_name:
        cprint(Color.RED, t("export_not_found", name=identifier))
        input(t("press_enter"))
        return
    filename = f"deployment_{dep_name}.yaml"
    if os.path.exists(filename):
        if not input_yes_no_text(t("export_save_overwrite", file=filename), default=False):
            cprint(Color.YELLOW, t("export_save_cancelled"))
            input(t("press_enter"))
            return
    cprint(Color.BLUE, t("export_fetching", name=dep_name))
    result = subprocess.run(['kubectl', 'get', 'deployment', dep_name, '-o', 'yaml'],
                            capture_output=True, text=True)
    if result.returncode != 0:
        cprint(Color.RED, t("export_fail", error=result.stderr))
    else:
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(result.stdout)
            cprint(Color.GREEN, t("export_save_success", file=filename))
        except Exception as e:
            cprint(Color.RED, t("export_fail", error=str(e)))
    input(t("press_enter"))

def export_deployment_menu():
    while True:
        print("\n" + t("export_deployment_menu_title"))
        print(t("export_deployment_1"))
        print(t("export_deployment_2"))
        print(t("export_deployment_3"))
        choice = input(t("export_deployment_prompt")).strip()
        if choice == '1':
            show_deployment_yaml()
        elif choice == '2':
            save_deployment_yaml()
        elif choice == '3':
            break
        else:
            cprint(Color.RED, t("invalid_option"))

# ---------- Edit Deployment Functions ----------
def edit_deployment_direct():
    while True:
        print("\n" + t("edit_deployment_direct_title"))
        numbered_list, dep_map, _ = get_deployment_list_with_numbers()
        if numbered_list is None or not numbered_list:
            cprint(Color.YELLOW, t("list_deployments_no_deployments"))
            input(t("press_enter"))
            return
        
        print(f"\n{Color.BOLD}{Color.CYAN}{'#':<4} {'Name':<30} {'Ready':<8} {'Available':<10} {'Image':<40}{Color.END}")
        print("-" * 100)
        for idx, name, data in numbered_list:
            image = data.get('images', 'N/A')
            if len(image) > 40:
                image = image[:37] + '...'
            print(f"{Color.GREEN}{idx:<4}{Color.END} {data['name']:<30} {data['ready']:<8} {data['available']:<10} {image:<40}")
        
        print(f"\n{Color.YELLOW}Enter 'q' to quit, 'menu' to return to Edit menu, or select a Deployment number/name.{Color.END}")
        identifier = input(t("edit_deployment_direct_prompt")).strip().lower()
        
        if identifier in ['q', 'quit']:
            cprint(Color.YELLOW, t("delete_exiting"))
            return
        if identifier in ['menu', 'back']:
            cprint(Color.YELLOW, t("delete_returning"))
            return
        
        dep_name = resolve_deployment_identifier(identifier, dep_map)
        if not dep_name:
            cprint(Color.RED, t("export_not_found", name=identifier))
            continue
        
        cprint(Color.BLUE, t("edit_deployment_direct_start", name=dep_name))
        result = subprocess.run(['kubectl', 'edit', 'deployment', dep_name])
        if result.returncode == 0:
            cprint(Color.GREEN, t("edit_deployment_direct_success"))
        else:
            cprint(Color.RED, t("edit_deployment_direct_fail"))
        input(t("press_enter"))
        return

def edit_deployment_yaml():
    print("\n" + t("edit_deployment_yaml_title"))
    numbered_list, dep_map, _ = get_deployment_list_with_numbers()
    if numbered_list is None or not numbered_list:
        cprint(Color.YELLOW, t("list_deployments_no_deployments"))
        input(t("press_enter"))
        return
    
    print(f"\n{Color.BOLD}{Color.CYAN}Available Deployments:{Color.END}")
    for idx, name, data in numbered_list:
        print(f"  {Color.GREEN}{idx}{Color.END}. {name} (Ready: {data['ready']})")
    
    identifier = input_required("describe_deployment_name")
    dep_name = resolve_deployment_identifier(identifier, dep_map)
    if not dep_name:
        cprint(Color.RED, t("export_not_found", name=identifier))
        input(t("press_enter"))
        return
    
    yaml_path = input(t("edit_deployment_yaml_path_prompt")).strip()
    if not yaml_path:
        cprint(Color.RED, t("edit_deployment_yaml_path_empty"))
        input(t("press_enter"))
        return
    
    if not os.path.exists(yaml_path):
        cprint(Color.RED, t("edit_deployment_yaml_not_found", path=yaml_path))
        input(t("press_enter"))
        return
    
    if input_yes_no_text(t("edit_deployment_yaml_edit_before"), default=True):
        cprint(Color.BLUE, t("edit_deployment_yaml_open_editor"))
        edit_yaml_with_vim(yaml_path)
    
    cprint(Color.BLUE, t("edit_deployment_yaml_applying"))
    result = subprocess.run(['kubectl', 'apply', '-f', yaml_path], capture_output=True, text=True)
    if result.returncode == 0:
        cprint(Color.GREEN, t("edit_deployment_yaml_success"))
        print(result.stdout)
    else:
        cprint(Color.RED, t("edit_deployment_yaml_fail"))
        print(result.stderr)
    input(t("press_enter"))

def edit_deployment_menu():
    while True:
        print("\n" + t("edit_deployment_menu_title"))
        print(t("edit_deployment_menu_1"))
        print(t("edit_deployment_menu_2"))
        print(t("edit_deployment_menu_3"))
        choice = input(t("edit_deployment_menu_prompt")).strip()
        if choice == '1':
            edit_deployment_direct()
        elif choice == '2':
            edit_deployment_yaml()
        elif choice == '3':
            break
        else:
            cprint(Color.RED, t("invalid_option"))

def create_deployment_menu():
    while True:
        print("\n" + t("create_deployment_submenu_title"))
        print(t("create_deployment_submenu_1"))
        print(t("create_deployment_submenu_2"))
        print(t("create_deployment_submenu_3"))
        choice = input(t("create_deployment_submenu_prompt")).strip()
        if choice == '1':
            quick_deploy_deployment()
        elif choice == '2':
            deployment_yaml_editor_mode()
        elif choice == '3':
            break
        else:
            cprint(Color.RED, t("invalid_option"))

def deployment_menu():
    while True:
        print("\n" + t("deployment_menu_title"))
        print(t("deployment_menu_1"))
        print(t("deployment_menu_2"))
        print(t("deployment_menu_3"))
        print(t("deployment_menu_4"))
        print(t("deployment_menu_5"))
        print(t("deployment_menu_6"))
        print(t("deployment_menu_7"))
        choice = input(t("deployment_menu_prompt")).strip()
        if choice == '1':
            create_deployment_menu()
        elif choice == '2':
            delete_deployment()
        elif choice == '3':
            list_deployments()
        elif choice == '4':
            describe_deployment()
        elif choice == '5':
            export_deployment_menu()
        elif choice == '6':
            edit_deployment_menu()
        elif choice == '7':
            break
        else:
            cprint(Color.RED, t("invalid_option"))
