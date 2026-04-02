#!/usr/bin/env python3
"""
Service management functions
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

def get_service_list_with_numbers():
    """Get numbered list of services, return (numbered_list, svc_map, output)"""
    result = subprocess.run(['kubectl', 'get', 'services', '-o', 'wide'], capture_output=True, text=True)
    if result.returncode != 0:
        return None, None, result.stderr
    lines = result.stdout.strip().split('\n')
    if len(lines) <= 1:
        return [], {}, None
    svc_data = []
    for line in lines[1:]:
        if line.strip():
            parts = line.split()
            if len(parts) >= 5:
                svc_data.append({
                    'name': parts[0],
                    'type': parts[1],
                    'cluster_ip': parts[2],
                    'external_ip': parts[3] if len(parts) > 3 else '<none>',
                    'ports': parts[4] if len(parts) > 4 else '',
                    'age': parts[5] if len(parts) > 5 else ''
                })
    svc_map = {}
    numbered_list = []
    for idx, data in enumerate(svc_data, 1):
        svc_map[str(idx)] = data['name']
        svc_map[data['name']] = data['name']
        numbered_list.append((idx, data['name'], data))
    return numbered_list, svc_map, result.stdout

def list_services_with_numbers():
    """Display numbered service list"""
    print("\n" + t("list_services_title"))
    numbered_list, _, output = get_service_list_with_numbers()
    if numbered_list is None:
        cprint(Color.RED, t("fail") + " " + t("list_services_fail") + ": " + output)
        return
    if not numbered_list:
        cprint(Color.YELLOW, t("list_services_no_services"))
        return
    print(f"{Color.BOLD}{Color.CYAN}{'#':<4} {'Name':<30} {'Type':<12} {'Cluster-IP':<16} {'External-IP':<16} {'Ports':<20} {'Age':<8}{Color.END}")
    print("-" * 110)
    for idx, name, data in numbered_list:
        print(f"{Color.GREEN}{idx:<4}{Color.END} {data['name']:<30} {data['type']:<12} {data['cluster_ip']:<16} {data['external_ip']:<16} {data['ports']:<20} {data['age']:<8}")
    return numbered_list

def get_deployment_list_for_service():
    """Get list of deployments for service creation (name, labels)"""
    result = subprocess.run(['kubectl', 'get', 'deployments', '-o', 'json'], capture_output=True, text=True)
    if result.returncode != 0:
        return []
    try:
        data = json.loads(result.stdout)
        deployments = []
        for item in data.get('items', []):
            name = item['metadata']['name']
            labels = item['metadata'].get('labels', {})
            if 'app' in labels:
                selector = f"app={labels['app']}"
            elif labels:
                first_key = list(labels.keys())[0]
                selector = f"{first_key}={labels[first_key]}"
            else:
                selector = f"app={name}"
            deployments.append({
                'name': name,
                'selector': selector,
                'labels': labels
            })
        return deployments
    except:
        return []

def quick_deploy_service():
    """Create Service by selecting an existing Deployment"""
    print("\n" + t("create_service_quick_title"))
    deployments = get_deployment_list_for_service()
    if not deployments:
        cprint(Color.YELLOW, "No Deployments found. Please create a Deployment first.")
        input(t("press_enter"))
        return
    
    print(f"\n{Color.BOLD}{Color.CYAN}Available Deployments:{Color.END}")
    for idx, dep in enumerate(deployments, 1):
        print(f"  {Color.GREEN}{idx}{Color.END}. {dep['name']} (selector: {dep['selector']})")
    
    identifier = input_required("create_service_select_deployment")
    if identifier.isdigit():
        idx = int(identifier) - 1
        if 0 <= idx < len(deployments):
            selected_dep = deployments[idx]
        else:
            cprint(Color.RED, "Invalid number.")
            input(t("press_enter"))
            return
    else:
        matches = [d for d in deployments if d['name'] == identifier]
        if not matches:
            cprint(Color.RED, t("export_not_found", name=identifier))
            input(t("press_enter"))
            return
        selected_dep = matches[0]
    
    name = input_required("create_service_name")
    svc_type = input_with_default("create_service_type", "ClusterIP")
    port = input_required("create_service_port")
    target_port = input_with_default("create_service_target_port", port)
    
    yaml_content = f"""apiVersion: v1
kind: Service
metadata:
  name: {name}
spec:
  type: {svc_type}
  selector:
    {selected_dep['selector'].replace('=', ': ')}
  ports:
  - port: {port}
    targetPort: {target_port}
"""
    apply_yaml(yaml_content)

def service_yaml_editor_mode():
    """Create Service by editing a YAML template"""
    print("\n" + t("create_service_yaml_title"))
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"service_{timestamp}.yaml"
    template = """# Kubernetes Service YAML Template
# Edit this file to create your Service

apiVersion: v1
kind: Service
metadata:
  name: my-service
spec:
  type: ClusterIP
  selector:
    app: my-app
  ports:
  - port: 80
    targetPort: 8080
"""
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

def create_service_menu():
    while True:
        print("\n" + t("create_service_submenu_title"))
        print(t("create_service_submenu_1"))
        print(t("create_service_submenu_2"))
        print(t("create_service_submenu_3"))
        choice = input(t("create_service_submenu_prompt")).strip()
        if choice == '1':
            quick_deploy_service()
        elif choice == '2':
            service_yaml_editor_mode()
        elif choice == '3':
            break
        else:
            cprint(Color.RED, t("invalid_option"))

def delete_service():
    while True:
        print("\n" + t("delete_service_title"))
        numbered_list, svc_map, _ = get_service_list_with_numbers()
        if numbered_list is None or not numbered_list:
            cprint(Color.YELLOW, t("delete_service_no_services"))
            return
        print(f"\n{Color.BOLD}{Color.CYAN}Current Services:{Color.END}")
        for idx, name, data in numbered_list:
            print(f"  {Color.GREEN}{idx}{Color.END}. {name} (Type: {data['type']})")
        print("\n" + t("delete_service_hint"))
        identifier = input(f"\n{t('delete_service_name')}: ").strip().lower()
        if identifier in ['q', 'quit']:
            cprint(Color.YELLOW, t("delete_exiting"))
            return
        if identifier in ['menu', 'back']:
            cprint(Color.YELLOW, t("delete_returning"))
            return
        if not identifier:
            cprint(Color.YELLOW, t("delete_no_input"))
            return
        svcs_to_delete = []
        if ' ' in identifier:
            parts = identifier.split()
            for part in parts:
                if part in svc_map:
                    svcs_to_delete.append(svc_map[part])
                elif part.isdigit():
                    cprint(Color.RED, t("delete_service_not_found", num=part))
                else:
                    cprint(Color.RED, t("delete_service_invalid"))
        else:
            svc_name = svc_map.get(identifier)
            if svc_name:
                svcs_to_delete.append(svc_name)
            else:
                if identifier.isdigit():
                    cprint(Color.RED, t("delete_service_not_found", num=identifier))
                else:
                    cprint(Color.RED, t("delete_service_invalid"))
                continue
        if not svcs_to_delete:
            cprint(Color.YELLOW, t("delete_no_valid"))
            continue
        print(f"\n{Color.YELLOW}Selected Services to delete:{Color.END}")
        for s in svcs_to_delete:
            print(f"  • {s}")
        if len(svcs_to_delete) == 1:
            confirm_msg = t("delete_service_confirm_single", name=svcs_to_delete[0])
        else:
            confirm_msg = t("delete_service_confirm_multiple", count=len(svcs_to_delete))
        if input_yes_no_text(confirm_msg, default=False):
            success = 0
            fail = 0
            for s in svcs_to_delete:
                result = subprocess.run(['kubectl', 'delete', 'service', s], capture_output=True, text=True)
                if result.returncode == 0:
                    cprint(Color.GREEN, t("delete_service_success", name=s))
                    success += 1
                else:
                    cprint(Color.RED, t("delete_service_fail", name=s, error=result.stderr.strip()))
                    fail += 1
            print(f"\n{Color.BOLD}{t('delete_service_summary')}{Color.END}")
            cprint(Color.GREEN, f"  ✅ Successfully deleted: {success}")
            if fail > 0:
                cprint(Color.RED, f"  ❌ Failed to delete: {fail}")
            if not input_yes_no_text(t("delete_more_prompt"), default=False):
                return
        else:
            cprint(Color.YELLOW, t("delete_cancelled"))
            if not input_yes_no_text(t("delete_try_again"), default=True):
                return

def list_services():
    list_services_with_numbers()
    input("\nPress Enter to continue...")

def describe_service():
    print("\n" + t("describe_service_title"))
    numbered_list, svc_map, _ = get_service_list_with_numbers()
    if numbered_list is None or not numbered_list:
        cprint(Color.YELLOW, "No Services available.")
        input(t("press_enter"))
        return
    print(f"\n{Color.BOLD}{Color.CYAN}Current Services:{Color.END}")
    for idx, name, data in numbered_list:
        print(f"  {Color.GREEN}{idx}{Color.END}. {name} (Type: {data['type']})")
    print("\n" + t("describe_service_hint"))
    identifier = input_required("describe_service_name")
    svc_name = svc_map.get(identifier)
    if not svc_name:
        if identifier.isdigit():
            cprint(Color.RED, t("delete_service_not_found", num=identifier))
        else:
            cprint(Color.RED, t("delete_service_invalid"))
        input(t("press_enter"))
        return
    cprint(Color.BLUE, t("describe_service_fetch", name=svc_name))
    result = subprocess.run(['kubectl', 'describe', 'service', svc_name], capture_output=True, text=True)
    if result.returncode == 0:
        print(result.stdout)
    else:
        cprint(Color.RED, t("fail") + " " + t("describe_service_fail") + ": " + result.stderr)
    input(t("press_enter"))

def service_menu():
    while True:
        print("\n" + t("service_menu_title"))
        print(t("service_menu_1"))
        print(t("service_menu_2"))
        print(t("service_menu_3"))
        print(t("service_menu_4"))
        print(t("service_menu_5"))
        choice = input(t("service_menu_prompt")).strip()
        if choice == '1':
            create_service_menu()
        elif choice == '2':
            delete_service()
        elif choice == '3':
            list_services()
        elif choice == '4':
            describe_service()
        elif choice == '5':
            break
        else:
            cprint(Color.RED, t("invalid_option"))
