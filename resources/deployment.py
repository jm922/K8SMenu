#!/usr/bin/env python3
"""
Deployment management functions
Refactored to use K8sClient for listing/querying and structured YAML generation
"""

import subprocess
import os
import yaml
from datetime import datetime

from utils.color import cprint, Color
from utils.lang import t
from utils.helpers import (
    input_required,
    input_with_default,
    input_yes_no,
    input_yes_no_text,
    apply_yaml,
)
from utils.yaml_helpers import (
    check_and_install_vim,
    edit_yaml_with_vim,
    validate_yaml_syntax,
    validate_with_kubectl,
    apply_yaml_file,
)
from resources.common import (
    get_deployment_list_with_numbers,
    resolve_deployment_identifier,
)
from k8s.client import K8sClient, K8sClientError

client = K8sClient()


def _truncate(text, length):
    text = "" if text is None else str(text)
    if len(text) <= length:
        return text
    return text[: length - 3] + "..."


def _format_age(creation_timestamp):
    """
    Keep it simple for now and return the raw timestamp.
    Later this can be converted to a human-readable age.
    """
    return creation_timestamp or ""


def list_deployments_with_numbers():
    """Display numbered list of Deployments with Labels column"""
    print("\n" + t("list_deployments_title"))

    try:
        items = client.get_items("deployments")
    except K8sClientError as e:
        cprint(Color.RED, t("fail") + " " + t("list_deployments_fail") + ": " + str(e))
        return None

    if not items:
        cprint(Color.YELLOW, t("list_deployments_no_deployments"))
        return None

    dep_data = []

    for item in items:
        metadata = item.get("metadata", {})
        spec = item.get("spec", {})
        status = item.get("status", {})

        name = metadata.get("name", "")
        labels_dict = metadata.get("labels", {})
        labels = ",".join([f"{k}={v}" for k, v in labels_dict.items()])

        desired = spec.get("replicas", 0)
        ready = status.get("readyReplicas", 0)
        updated = status.get("updatedReplicas", 0)
        available = status.get("availableReplicas", 0)

        containers = spec.get("template", {}).get("spec", {}).get("containers", [])
        container_names = ",".join([c.get("name", "") for c in containers])
        image_names = ",".join([c.get("image", "") for c in containers])

        creation_time = metadata.get("creationTimestamp", "")

        dep_data.append(
            {
                "name": name,
                "ready": f"{ready}/{desired}",
                "up_to_date": str(updated),
                "available": str(available),
                "age": _format_age(creation_time),
                "containers": container_names,
                "images": image_names,
                "labels": labels,
            }
        )

    print(
        f"{Color.BOLD}{Color.CYAN}"
        f"{'#':<4} {'Name':<30} {'Ready':<8} {'Up-to-date':<10} "
        f"{'Available':<10} {'Age':<20} {'Image':<40} {'Labels':<30}"
        f"{Color.END}"
    )
    print("-" * 160)

    for idx, data in enumerate(dep_data, 1):
        image = _truncate(data["images"], 40)
        labels = _truncate(data["labels"], 30)

        print(
            f"{Color.GREEN}{idx:<4}{Color.END} "
            f"{data['name']:<30} "
            f"{data['ready']:<8} "
            f"{data['up_to_date']:<10} "
            f"{data['available']:<10} "
            f"{data['age']:<20} "
            f"{image:<40} "
            f"{labels:<30}"
        )

    numbered_list = [(idx, d["name"], d) for idx, d in enumerate(dep_data, 1)]
    dep_map = {str(idx): d["name"] for idx, d in enumerate(dep_data, 1)}
    dep_map.update({d["name"]: d["name"] for d in dep_data})
    return numbered_list, dep_map


def show_deployment_pods(dep_name=None):
    """Show Pods belonging to a specific Deployment"""
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

    try:
        dep_json = client.get_json("deployment", extra_args=[dep_name])
    except K8sClientError as e:
        cprint(Color.RED, f"Failed to get deployment JSON: {e}")
        input(t("press_enter"))
        return

    selector = dep_json.get("spec", {}).get("selector", {}).get("matchLabels", {})
    if not selector:
        selector = {"app": dep_name}

    label_selector = ",".join([f"{k}={v}" for k, v in selector.items()])

    try:
        pod_items = client.get_items("pods", extra_args=["-l", label_selector])
    except K8sClientError as e:
        cprint(Color.RED, f"Failed to get pods: {e}")
        input(t("press_enter"))
        return

    print(f"\n{Color.BOLD}{Color.CYAN}Pods for Deployment '{dep_name}' (selector: {label_selector}):{Color.END}")

    if not pod_items:
        cprint(Color.YELLOW, "No pods found.")
        input(t("press_enter"))
        return

    print(
        f"{Color.BOLD}{Color.CYAN}"
        f"{'Pod Name':<30} {'Ready':<8} {'Restarts':<10} {'Status':<24} "
        f"{'IP':<16} {'Node':<20} {'Labels':<30}"
        f"{Color.END}"
    )
    print("-" * 150)

    for item in pod_items:
        metadata = item.get("metadata", {})
        status = item.get("status", {})
        spec = item.get("spec", {})

        name = metadata.get("name", "")
        phase = status.get("phase", "")
        pod_ip = status.get("podIP", "")
        node_name = spec.get("nodeName", "")

        container_statuses = status.get("containerStatuses", [])
        total_containers = len(container_statuses)
        ready_containers = sum(1 for c in container_statuses if c.get("ready"))
        restart_count = sum(c.get("restartCount", 0) for c in container_statuses)
        ready = f"{ready_containers}/{total_containers}" if total_containers > 0 else "0/0"

        labels_dict = metadata.get("labels", {})
        labels = ",".join([f"{k}={v}" for k, v in labels_dict.items()])
        labels = _truncate(labels, 30)

        print(
            f"{name:<30} "
            f"{ready:<8} "
            f"{str(restart_count):<10} "
            f"{_truncate(phase, 24):<24} "
            f"{pod_ip:<16} "
            f"{node_name:<20} "
            f"{labels:<30}"
        )

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
        if identifier in ["q", "quit"]:
            return

        dep_name = resolve_deployment_identifier(identifier, dep_map)
        if dep_name:
            show_deployment_pods(dep_name)
            return
        else:
            cprint(Color.RED, t("export_not_found", name=identifier))

    input("\nPress Enter to continue...")


def quick_deploy_deployment():
    """
    Production-ready basic Deployment creator
    Supports: env, resources, probes
    """
    print("\n" + t("create_deployment_title"))

    name = input_required("create_deployment_name")
    image = input_required("create_deployment_image")
    replicas = input_with_default("create_deployment_replicas", "1")
    port = input_with_default("create_deployment_port", "80")

    try:
        replicas = int(replicas)
        port = int(port)
    except ValueError:
        cprint(Color.RED, "Replicas and port must be numbers")
        input(t("press_enter"))
        return

    # ENV
    env_vars = []
    while input_yes_no("create_deployment_env_ask", False):
        key = input_required("create_deployment_env_key")
        value = input_required("create_deployment_env_value")
        env_vars.append({"name": key, "value": value})

    # RESOURCES
    resources = None
    if input_yes_no_text("Set resource limits?", False):
        cpu_req = input("CPU request (e.g. 100m) [default: 100m]: ").strip() or "100m"
        mem_req = input("Memory request (e.g. 128Mi) [default: 128Mi]: ").strip() or "128Mi"
        cpu_lim = input("CPU limit (e.g. 300m) [default: 300m]: ").strip() or "300m"
        mem_lim = input("Memory limit (e.g. 256Mi) [default: 256Mi]: ").strip() or "256Mi"

        resources = {
            "requests": {
                "cpu": cpu_req,
                "memory": mem_req,
            },
            "limits": {
                "cpu": cpu_lim,
                "memory": mem_lim,
            },
        }

    # PROBES
    probes = {}

    if input_yes_no_text("Enable readinessProbe?", False):
        path = input("HTTP path [default: /]: ").strip() or "/"
        probes["readinessProbe"] = {
            "httpGet": {
                "path": path,
                "port": port,
            },
            "initialDelaySeconds": 5,
            "periodSeconds": 10,
        }

    if input_yes_no_text("Enable livenessProbe?", False):
        path = input("HTTP path [default: /]: ").strip() or "/"
        probes["livenessProbe"] = {
            "httpGet": {
                "path": path,
                "port": port,
            },
            "initialDelaySeconds": 10,
            "periodSeconds": 20,
        }

    container = {
        "name": name,
        "image": image,
        "imagePullPolicy": "IfNotPresent",
        "ports": [
            {
                "containerPort": port
            }
        ],
    }

    if env_vars:
        container["env"] = env_vars

    if resources:
        container["resources"] = resources

    container.update(probes)

    deployment = {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {
            "name": name,
            "labels": {
                "app": name
            },
        },
        "spec": {
            "replicas": replicas,
            "selector": {
                "matchLabels": {
                    "app": name
                }
            },
            "template": {
                "metadata": {
                    "labels": {
                        "app": name
                    }
                },
                "spec": {
                    "containers": [container]
                },
            },
        },
    }

    yaml_content = yaml.safe_dump(deployment, sort_keys=False)

    print("\nGenerated YAML:\n")
    print(yaml_content)

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
        # resources:
        #   requests:
        #     cpu: "100m"
        #     memory: "128Mi"
        #   limits:
        #     cpu: "300m"
        #     memory: "256Mi"
"""
    return filename, template


def deployment_yaml_editor_mode():
    print("\n" + t("deployment_yaml_editor_title"))
    filename, template = generate_deployment_template()

    with open(filename, "w", encoding="utf-8") as f:
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

        if identifier in ["q", "quit"]:
            cprint(Color.YELLOW, t("delete_exiting"))
            return
        if identifier in ["menu", "back"]:
            cprint(Color.YELLOW, t("delete_returning"))
            return
        if not identifier:
            cprint(Color.YELLOW, t("delete_no_input"))
            return

        deps_to_delete = []

        if " " in identifier:
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
                result = subprocess.run(["kubectl", "delete", "deployment", d], capture_output=True, text=True)
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
    result = subprocess.run(["kubectl", "describe", "deployment", dep_name], capture_output=True, text=True)

    if result.returncode == 0:
        print(result.stdout)
    else:
        cprint(Color.RED, t("fail") + " " + t("describe_deployment_fail") + ": " + result.stderr)

    input(t("press_enter"))


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
    result = subprocess.run(["kubectl", "get", "deployment", dep_name, "-o", "yaml"], capture_output=True, text=True)

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
    result = subprocess.run(["kubectl", "get", "deployment", dep_name, "-o", "yaml"], capture_output=True, text=True)

    if result.returncode != 0:
        cprint(Color.RED, t("export_fail", error=result.stderr))
    else:
        try:
            with open(filename, "w", encoding="utf-8") as f:
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

        if choice == "1":
            show_deployment_yaml()
        elif choice == "2":
            save_deployment_yaml()
        elif choice == "3":
            break
        else:
            cprint(Color.RED, t("invalid_option"))


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
            image = data.get("images", "N/A")
            if len(image) > 40:
                image = image[:37] + "..."
            print(f"{Color.GREEN}{idx:<4}{Color.END} {data['name']:<30} {data['ready']:<8} {data['available']:<10} {image:<40}")

        print(f"\n{Color.YELLOW}Enter 'q' to quit, 'menu' to return to Edit menu, or select a Deployment number/name.{Color.END}")
        identifier = input(t("edit_deployment_direct_prompt")).strip().lower()

        if identifier in ["q", "quit"]:
            cprint(Color.YELLOW, t("delete_exiting"))
            return
        if identifier in ["menu", "back"]:
            cprint(Color.YELLOW, t("delete_returning"))
            return

        dep_name = resolve_deployment_identifier(identifier, dep_map)
        if not dep_name:
            cprint(Color.RED, t("export_not_found", name=identifier))
            continue

        cprint(Color.BLUE, t("edit_deployment_direct_start", name=dep_name))
        result = subprocess.run(["kubectl", "edit", "deployment", dep_name])

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
    result = subprocess.run(["kubectl", "apply", "-f", yaml_path], capture_output=True, text=True)

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

        if choice == "1":
            edit_deployment_direct()
        elif choice == "2":
            edit_deployment_yaml()
        elif choice == "3":
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

        if choice == "1":
            quick_deploy_deployment()
        elif choice == "2":
            deployment_yaml_editor_mode()
        elif choice == "3":
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

        if choice == "1":
            create_deployment_menu()
        elif choice == "2":
            delete_deployment()
        elif choice == "3":
            list_deployments()
        elif choice == "4":
            describe_deployment()
        elif choice == "5":
            export_deployment_menu()
        elif choice == "6":
            edit_deployment_menu()
        elif choice == "7":
            break
        else:
            cprint(Color.RED, t("invalid_option"))
