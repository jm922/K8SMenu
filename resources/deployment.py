#!/usr/bin/env python3
"""
Deployment management functions.
English-only comments and print messages.
"""

import os
import shutil
import shlex
import subprocess
import tempfile
from datetime import datetime

import yaml

from utils.color import cprint, Color
from resources.common import resolve_deployment_identifier
from k8s.client import K8sClient, K8sClientError

client = K8sClient()


def _pause():
    input("\nPress Enter to continue...")


def _input_required(prompt):
    while True:
        value = input(f"{prompt}: ").strip()
        if value:
            return value
        cprint(Color.YELLOW, "Input cannot be empty.")


def _input_default(prompt, default):
    value = input(f"{prompt} [default: {default}]: ").strip()
    return value or default


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


def _format_age(creation_timestamp):
    """
    Keep the raw timestamp for now.
    A human-readable age can be added later.
    """
    return creation_timestamp or ""


def _apply_yaml_content(yaml_content):
    """
    Apply YAML content to the cluster with English-only messages.
    """
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8") as f:
            f.write(yaml_content)
            tmp_path = f.name

        print("\nApplying configuration to cluster...")
        result = subprocess.run(
            ["kubectl", "apply", "-f", tmp_path],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            cprint(Color.GREEN, "Success: " + result.stdout.strip())
            return True

        cprint(Color.RED, "Failed to apply configuration:")
        if result.stderr.strip():
            print(result.stderr.strip())
        else:
            print("Unknown kubectl apply error.")
        return False

    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


def _ensure_vim_installed():
    if shutil.which("vim"):
        return True
    cprint(Color.RED, "vim is not installed. Please install vim first.")
    return False


def _open_in_vim(filepath):
    result = subprocess.run(["vim", filepath])
    return result.returncode == 0


def _validate_yaml_syntax(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            list(yaml.safe_load_all(f))
        return True, None
    except Exception as e:
        return False, str(e)


def _validate_with_kubectl(filepath):
    result = subprocess.run(
        ["kubectl", "apply", "--dry-run=client", "-f", filepath],
        capture_output=True,
        text=True
    )
    return result.returncode == 0, result.stderr.strip()


def list_deployments_with_numbers():
    """
    Display numbered list of Deployments with labels.
    """
    print("\n--- Current Deployment List ---")

    try:
        items = client.get_items("deployments")
    except K8sClientError as e:
        cprint(Color.RED, f"Failed to list deployments: {e}")
        return None

    if not items:
        cprint(Color.YELLOW, "No deployments found.")
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
        image_names = ",".join([c.get("image", "") for c in containers])

        creation_time = metadata.get("creationTimestamp", "")

        dep_data.append(
            {
                "name": name,
                "ready": f"{ready}/{desired}",
                "up_to_date": str(updated),
                "available": str(available),
                "age": _format_age(creation_time),
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
    """
    Show Pods that belong to a specific Deployment.
    """
    if dep_name is None:
        result = list_deployments_with_numbers()
        if result is None:
            return

        numbered_list, dep_map = result
        if not numbered_list:
            cprint(Color.YELLOW, "No deployments found.")
            _pause()
            return

        print(f"\n{Color.BOLD}{Color.CYAN}Available Deployments:{Color.END}")
        for idx, name, data in numbered_list:
            print(f"  {Color.GREEN}{idx}{Color.END}. {name} (Ready: {data['ready']})")

        identifier = _input_required("Enter deployment number or name")
        dep_name = resolve_deployment_identifier(identifier, dep_map)

        if not dep_name:
            cprint(Color.RED, f"Deployment not found: {identifier}")
            _pause()
            return

    try:
        dep_json = client.get_json("deployment", extra_args=[dep_name])
    except K8sClientError as e:
        cprint(Color.RED, f"Failed to get deployment details: {e}")
        _pause()
        return

    selector = dep_json.get("spec", {}).get("selector", {}).get("matchLabels", {})
    if not selector:
        selector = {"app": dep_name}

    label_selector = ",".join([f"{k}={v}" for k, v in selector.items()])

    try:
        pod_items = client.get_items("pods", extra_args=["-l", label_selector])
    except K8sClientError as e:
        cprint(Color.RED, f"Failed to get pods: {e}")
        _pause()
        return

    print(f"\nPods for Deployment '{dep_name}' (selector: {label_selector}):")

    if not pod_items:
        cprint(Color.YELLOW, "No pods found.")
        _pause()
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

    _pause()


def list_deployments():
    """
    List all Deployments and optionally show Pods for one Deployment.
    """
    result = list_deployments_with_numbers()
    if result is None:
        return

    numbered_list, dep_map = result
    if not numbered_list:
        return

    if _input_yes_no("Do you want to see pods of a deployment?", default=False):
        print("Enter deployment number or name to show pods (or 'q' to quit):")
        identifier = input("").strip().lower()
        if identifier in ["q", "quit"]:
            return

        dep_name = resolve_deployment_identifier(identifier, dep_map)
        if dep_name:
            show_deployment_pods(dep_name)
            return

        cprint(Color.RED, f"Deployment not found: {identifier}")

    _pause()


# NOTE:
# Current Quick Deploy probe support is basic only.
# It is good for simple testing, but it should be enhanced later.
# Planned improvements:
# 1. Support tcpSocket and exec probes
# 2. Support separate readiness and liveness strategies
# 3. Support custom initialDelaySeconds / periodSeconds / timeoutSeconds / failureThreshold
# 4. Support production-friendly endpoints such as /ready /live /health
def quick_deploy_deployment():
    """
    Basic production-friendly Deployment creator.
    Supports env, resources, readinessProbe, and livenessProbe.
    """
    print("\n--- Create Deployment (Quick Deploy) ---")

    name = _input_required("Deployment name")
    image = _input_required("Image (e.g., nginx:latest)")
    replicas = _input_default("Number of replicas", "1")
    port = _input_default("Container port", "80")

    try:
        replicas = int(replicas)
        port = int(port)
    except ValueError:
        cprint(Color.RED, "Replicas and port must be numbers.")
        _pause()
        return

    env_vars = []
    while _input_yes_no("Add environment variables?", default=False):
        key = _input_required("  Environment variable name")
        value = _input_required("  Environment variable value")
        env_vars.append({"name": key, "value": value})

    resources = None
    if _input_yes_no("Set resource limits?", default=False):
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

    probes = {}

    if _input_yes_no("Enable readinessProbe?", default=False):
        path = input("HTTP path [default: /]: ").strip() or "/"
        probes["readinessProbe"] = {
            "httpGet": {
                "path": path,
                "port": port,
            },
            "initialDelaySeconds": 5,
            "periodSeconds": 10,
        }

    if _input_yes_no("Enable livenessProbe?", default=False):
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

    _apply_yaml_content(yaml_content)
    _pause()


def scale_deployment():
    """
    Scale a Deployment to a new replica count.
    Show the full kubectl scale command before execution.
    """
    print(f"\n{Color.BOLD}{Color.CYAN}--- Scale Deployment ---{Color.END}")

    result = list_deployments_with_numbers()
    if result is None:
        cprint(Color.YELLOW, "No deployments available.")
        _pause()
        return

    numbered_list, dep_map = result
    if not numbered_list:
        cprint(Color.YELLOW, "No deployments available.")
        _pause()
        return

    identifier = _input_required("Enter deployment number or name to scale")
    dep_name = resolve_deployment_identifier(identifier, dep_map)

    if not dep_name:
        cprint(Color.RED, f"Deployment not found: {identifier}")
        _pause()
        return

    try:
        dep_json = client.get_json("deployment", extra_args=[dep_name])
    except K8sClientError as e:
        cprint(Color.RED, f"Failed to get deployment details: {e}")
        _pause()
        return

    current_replicas = dep_json.get("spec", {}).get("replicas", 0)

    print(f"\n{Color.BOLD}{Color.CYAN}Current deployment{Color.END}")
    print(f"{Color.BLUE}Name:{Color.END}             {dep_name}")
    print(f"{Color.BLUE}Current replicas:{Color.END} {Color.YELLOW}{current_replicas}{Color.END}")

    new_replicas_raw = _input_required("Enter new replica count")
    try:
        new_replicas = int(new_replicas_raw)
    except ValueError:
        cprint(Color.RED, "Replica count must be an integer.")
        _pause()
        return

    if new_replicas < 0:
        cprint(Color.RED, "Replica count cannot be negative.")
        _pause()
        return

    if new_replicas == current_replicas:
        cprint(Color.YELLOW, f"Replica count is already {current_replicas}. No changes applied.")
        _pause()
        return

    scale_cmd = [
        "kubectl",
        "scale",
        "deployment",
        dep_name,
        f"--replicas={new_replicas}"
    ]
    cmd_display = " ".join(shlex.quote(part) for part in scale_cmd)

    print(f"\n{Color.BOLD}{Color.CYAN}Scale operation preview{Color.END}")
    print(f"{Color.BLUE}Deployment:{Color.END}       {dep_name}")
    print(f"{Color.BLUE}Current replicas:{Color.END} {current_replicas}")
    print(f"{Color.BLUE}Target replicas:{Color.END}  {Color.YELLOW}{new_replicas}{Color.END}")
    print()
    print(f"{Color.BOLD}{Color.YELLOW}kubectl command:{Color.END}")
    print(f"{Color.YELLOW}{cmd_display}{Color.END}")

    if not _input_yes_no("Proceed with scale operation?", default=True):
        cprint(Color.YELLOW, "Scale operation cancelled.")
        _pause()
        return

    result = subprocess.run(
        scale_cmd,
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print()
        cprint(Color.RED, "Failed to scale deployment.")
        if result.stderr.strip():
            print(f"{Color.RED}{result.stderr.strip()}{Color.END}")
        _pause()
        return

    print()
    cprint(Color.GREEN, "Scale command applied successfully.")

    if result.stdout.strip():
        print(f"{Color.BOLD}{Color.GREEN}kubectl output:{Color.END}")
        print(f"{Color.GREEN}{result.stdout.strip()}{Color.END}")

    try:
        updated_json = client.get_json("deployment", extra_args=[dep_name])
    except K8sClientError as e:
        cprint(Color.YELLOW, f"Scaled, but failed to fetch updated deployment state: {e}")
        _pause()
        return

    desired = updated_json.get("spec", {}).get("replicas", 0)
    status = updated_json.get("status", {})
    ready = status.get("readyReplicas", 0)
    available = status.get("availableReplicas", 0)
    updated = status.get("updatedReplicas", 0)

    print(f"\n{Color.BOLD}{Color.CYAN}Updated deployment status{Color.END}")
    print(f"{Color.BLUE}Deployment:{Color.END}       {dep_name}")
    print(f"{Color.BLUE}Desired replicas:{Color.END} {desired}")
    print(f"{Color.BLUE}Updated replicas:{Color.END} {updated}")
    print(f"{Color.BLUE}Ready replicas:{Color.END}   {ready}")
    print(f"{Color.BLUE}Available:{Color.END}        {available}")

    if desired != ready or desired != available:
        print()
        cprint(Color.YELLOW, "Scaling is still in progress. Final readiness may take a few more seconds.")

    _pause()


def rollout_status_deployment():
    """
    Show rollout status for a selected Deployment.
    """
    print(f"\n{Color.BOLD}{Color.CYAN}--- Rollout Status ---{Color.END}")

    result = list_deployments_with_numbers()
    if result is None:
        cprint(Color.YELLOW, "No deployments available.")
        _pause()
        return

    numbered_list, dep_map = result
    if not numbered_list:
        cprint(Color.YELLOW, "No deployments available.")
        _pause()
        return

    identifier = _input_required("Enter deployment number or name")
    dep_name = resolve_deployment_identifier(identifier, dep_map)

    if not dep_name:
        cprint(Color.RED, f"Deployment not found: {identifier}")
        _pause()
        return

    timeout = _input_default("Enter rollout timeout", "60s")

    rollout_cmd = [
        "kubectl",
        "rollout",
        "status",
        f"deployment/{dep_name}",
        f"--timeout={timeout}"
    ]
    cmd_display = " ".join(shlex.quote(part) for part in rollout_cmd)

    print(f"\n{Color.BOLD}{Color.CYAN}Rollout status preview{Color.END}")
    print(f"{Color.BLUE}Deployment:{Color.END} {dep_name}")
    print(f"{Color.BLUE}Timeout:{Color.END}    {Color.YELLOW}{timeout}{Color.END}")
    print()
    print(f"{Color.BOLD}{Color.YELLOW}kubectl command:{Color.END}")
    print(f"{Color.YELLOW}{cmd_display}{Color.END}")

    if not _input_yes_no("Proceed with rollout status check?", default=True):
        cprint(Color.YELLOW, "Rollout status check cancelled.")
        _pause()
        return

    print()
    cprint(Color.CYAN, "Checking rollout status...")

    result = subprocess.run(
        rollout_cmd,
        capture_output=True,
        text=True
    )

    print()

    if result.returncode == 0:
        cprint(Color.GREEN, "Rollout status completed successfully.")
        if result.stdout.strip():
            print(f"{Color.BOLD}{Color.GREEN}kubectl output:{Color.END}")
            print(f"{Color.GREEN}{result.stdout.strip()}{Color.END}")
    else:
        cprint(Color.RED, "Rollout status check failed or timed out.")
        if result.stderr.strip():
            print(f"{Color.RED}{result.stderr.strip()}{Color.END}")
        elif result.stdout.strip():
            print(f"{Color.RED}{result.stdout.strip()}{Color.END}")

    try:
        dep_json = client.get_json("deployment", extra_args=[dep_name])
        desired = dep_json.get("spec", {}).get("replicas", 0)
        status = dep_json.get("status", {})
        updated = status.get("updatedReplicas", 0)
        ready = status.get("readyReplicas", 0)
        available = status.get("availableReplicas", 0)

        print(f"\n{Color.BOLD}{Color.CYAN}Current deployment status{Color.END}")
        print(f"{Color.BLUE}Deployment:{Color.END}       {dep_name}")
        print(f"{Color.BLUE}Desired replicas:{Color.END} {desired}")
        print(f"{Color.BLUE}Updated replicas:{Color.END} {updated}")
        print(f"{Color.BLUE}Ready replicas:{Color.END}   {ready}")
        print(f"{Color.BLUE}Available:{Color.END}        {available}")

    except K8sClientError as e:
        cprint(Color.YELLOW, f"Failed to fetch deployment details after rollout check: {e}")

    _pause()


def generate_deployment_template():
    """
    Generate a basic Deployment YAML template file name and content.
    """
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
        # readinessProbe:
        #   httpGet:
        #     path: /
        #     port: 80
        #   initialDelaySeconds: 5
        #   periodSeconds: 10
        # livenessProbe:
        #   httpGet:
        #     path: /
        #     port: 80
        #   initialDelaySeconds: 10
        #   periodSeconds: 20
"""
    return filename, template


def deployment_yaml_editor_mode():
    """
    Create a YAML template file, open it in vim, validate it, and apply it.
    """
    print("\n--- Create Deployment (YAML Editor Mode) ---")
    filename, template = generate_deployment_template()

    with open(filename, "w", encoding="utf-8") as f:
        f.write(template)

    cprint(Color.GREEN, f"Template file created: {filename}")

    if not _ensure_vim_installed():
        return

    if not _open_in_vim(filename):
        cprint(Color.RED, "Failed to open vim.")
        return

    while True:
        valid, err = _validate_yaml_syntax(filename)
        if not valid:
            cprint(Color.RED, f"YAML syntax validation failed: {err}")
            if not _input_yes_no("Edit the file again?", default=True):
                cprint(Color.YELLOW, f"Aborted. File kept: {filename}")
                return
            _open_in_vim(filename)
            continue

        kubectl_valid, kubectl_err = _validate_with_kubectl(filename)
        if not kubectl_valid:
            cprint(Color.RED, f"kubectl validation failed: {kubectl_err}")
            if not _input_yes_no("Edit the file again?", default=True):
                cprint(Color.YELLOW, f"Aborted. File kept: {filename}")
                return
            _open_in_vim(filename)
            continue

        break

    result = subprocess.run(
        ["kubectl", "apply", "-f", filename],
        capture_output=True,
        text=True
    )

    if result.returncode == 0:
        cprint(Color.GREEN, "Deployment applied successfully.")
        if result.stdout.strip():
            print(result.stdout.strip())
    else:
        cprint(Color.RED, "Failed to apply deployment.")
        if result.stderr.strip():
            print(result.stderr.strip())

    _pause()


def delete_deployment():
    """
    Delete one or more Deployments by number or name.
    """
    while True:
        result = list_deployments_with_numbers()
        if result is None:
            cprint(Color.YELLOW, "No deployments available.")
            return

        numbered_list, dep_map = result
        if not numbered_list:
            cprint(Color.YELLOW, "No deployments available.")
            return

        print("\nEnter one or more deployment numbers/names separated by spaces.")
        print("Enter 'q' to quit or 'menu' to go back.")
        identifier = input("\nDeployment number or name to delete: ").strip().lower()

        if identifier in ["q", "quit"]:
            cprint(Color.YELLOW, "Exiting delete mode.")
            return
        if identifier in ["menu", "back"]:
            cprint(Color.YELLOW, "Returning to menu.")
            return
        if not identifier:
            cprint(Color.YELLOW, "No input provided.")
            return

        deps_to_delete = []

        if " " in identifier:
            parts = identifier.split()
            for part in parts:
                if part in dep_map:
                    deps_to_delete.append(dep_map[part])
                else:
                    cprint(Color.RED, f"Deployment not found: {part}")
        else:
            dep_name = resolve_deployment_identifier(identifier, dep_map)
            if dep_name:
                deps_to_delete.append(dep_name)
            else:
                cprint(Color.RED, f"Deployment not found: {identifier}")
                continue

        if not deps_to_delete:
            cprint(Color.YELLOW, "No valid deployments selected.")
            continue

        print("\nSelected Deployments:")
        for dep in deps_to_delete:
            print(f"  - {dep}")

        if _input_yes_no("Confirm deletion?", default=False):
            success = 0
            failed = 0

            for dep in deps_to_delete:
                result = subprocess.run(
                    ["kubectl", "delete", "deployment", dep],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    cprint(Color.GREEN, f"Deleted deployment: {dep}")
                    success += 1
                else:
                    cprint(Color.RED, f"Failed to delete deployment: {dep}")
                    if result.stderr.strip():
                        print(result.stderr.strip())
                    failed += 1

            print("\nDelete summary:")
            cprint(Color.GREEN, f"  Success: {success}")
            if failed > 0:
                cprint(Color.RED, f"  Failed: {failed}")

            if not _input_yes_no("Delete more deployments?", default=False):
                return
        else:
            cprint(Color.YELLOW, "Deletion cancelled.")
            if not _input_yes_no("Try again?", default=True):
                return


def describe_deployment():
    """
    Show 'kubectl describe deployment' output for a selected Deployment.
    """
    result = list_deployments_with_numbers()
    if result is None:
        cprint(Color.YELLOW, "No deployments available.")
        _pause()
        return

    numbered_list, dep_map = result
    if not numbered_list:
        cprint(Color.YELLOW, "No deployments available.")
        _pause()
        return

    identifier = _input_required("Enter deployment number or name to view details")
    dep_name = resolve_deployment_identifier(identifier, dep_map)

    if not dep_name:
        cprint(Color.RED, f"Deployment not found: {identifier}")
        _pause()
        return

    print(f"Fetching details for deployment '{dep_name}'...")
    result = subprocess.run(
        ["kubectl", "describe", "deployment", dep_name],
        capture_output=True,
        text=True
    )

    if result.returncode == 0:
        print(result.stdout)
    else:
        cprint(Color.RED, f"Failed to view deployment details: {dep_name}")
        if result.stderr.strip():
            print(result.stderr.strip())

    _pause()


def show_deployment_yaml():
    """
    Print deployment YAML to the screen.
    """
    result = list_deployments_with_numbers()
    if result is None:
        cprint(Color.YELLOW, "No deployments available.")
        return

    numbered_list, dep_map = result
    if not numbered_list:
        cprint(Color.YELLOW, "No deployments available.")
        return

    identifier = _input_required("Enter deployment number or name to display YAML")
    dep_name = resolve_deployment_identifier(identifier, dep_map)

    if not dep_name:
        cprint(Color.RED, f"Deployment not found: {identifier}")
        _pause()
        return

    result = subprocess.run(
        ["kubectl", "get", "deployment", dep_name, "-o", "yaml"],
        capture_output=True,
        text=True
    )

    if result.returncode == 0:
        print("\nDeployment YAML:\n")
        print(result.stdout)
    else:
        cprint(Color.RED, f"Failed to export YAML for deployment: {dep_name}")
        if result.stderr.strip():
            print(result.stderr.strip())

    _pause()


def save_deployment_yaml():
    """
    Save deployment YAML to a local file.
    """
    result = list_deployments_with_numbers()
    if result is None:
        cprint(Color.YELLOW, "No deployments available.")
        return

    numbered_list, dep_map = result
    if not numbered_list:
        cprint(Color.YELLOW, "No deployments available.")
        return

    identifier = _input_required("Enter deployment number or name to save YAML")
    dep_name = resolve_deployment_identifier(identifier, dep_map)

    if not dep_name:
        cprint(Color.RED, f"Deployment not found: {identifier}")
        _pause()
        return

    filename = f"deployment_{dep_name}.yaml"
    if os.path.exists(filename):
        if not _input_yes_no(f"File '{filename}' already exists. Overwrite?", default=False):
            cprint(Color.YELLOW, "Save cancelled.")
            _pause()
            return

    result = subprocess.run(
        ["kubectl", "get", "deployment", dep_name, "-o", "yaml"],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        cprint(Color.RED, f"Failed to export YAML for deployment: {dep_name}")
        if result.stderr.strip():
            print(result.stderr.strip())
        _pause()
        return

    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write(result.stdout)
        cprint(Color.GREEN, f"YAML saved successfully: {filename}")
    except Exception as e:
        cprint(Color.RED, f"Failed to save YAML file: {e}")

    _pause()


def export_deployment_menu():
    """
    Export Deployment menu.
    """
    while True:
        print("\n--- Export Deployment YAML ---")
        print("1. Show Deployment YAML")
        print("2. Save Deployment YAML to file")
        print("3. Back")
        choice = input("Choose (1-3): ").strip()

        if choice == "1":
            show_deployment_yaml()
        elif choice == "2":
            save_deployment_yaml()
        elif choice == "3":
            break
        else:
            cprint(Color.RED, "Invalid option.")


def edit_deployment_direct():
    """
    Use 'kubectl edit deployment' directly.
    """
    while True:
        result = list_deployments_with_numbers()
        if result is None:
            cprint(Color.YELLOW, "No deployments available.")
            _pause()
            return

        numbered_list, dep_map = result
        if not numbered_list:
            cprint(Color.YELLOW, "No deployments available.")
            _pause()
            return

        print("\nEnter 'q' to quit, 'menu' to return, or select a deployment number/name.")
        identifier = input("Deployment number or name to edit directly: ").strip().lower()

        if identifier in ["q", "quit"]:
            cprint(Color.YELLOW, "Exiting direct edit mode.")
            return
        if identifier in ["menu", "back"]:
            cprint(Color.YELLOW, "Returning to menu.")
            return

        dep_name = resolve_deployment_identifier(identifier, dep_map)
        if not dep_name:
            cprint(Color.RED, f"Deployment not found: {identifier}")
            continue

        cprint(Color.BLUE, f"Opening deployment '{dep_name}' in kubectl edit...")
        result = subprocess.run(["kubectl", "edit", "deployment", dep_name])

        if result.returncode == 0:
            cprint(Color.GREEN, "Deployment edited successfully.")
        else:
            cprint(Color.RED, "Failed to edit deployment.")

        _pause()
        return


def edit_deployment_yaml():
    """
    Apply updates to a deployment from a local YAML file.
    """
    result = list_deployments_with_numbers()
    if result is None:
        cprint(Color.YELLOW, "No deployments available.")
        _pause()
        return

    numbered_list, dep_map = result
    if not numbered_list:
        cprint(Color.YELLOW, "No deployments available.")
        _pause()
        return

    identifier = _input_required("Enter deployment number or name")
    dep_name = resolve_deployment_identifier(identifier, dep_map)

    if not dep_name:
        cprint(Color.RED, f"Deployment not found: {identifier}")
        _pause()
        return

    yaml_path = input("Enter YAML file path: ").strip()
    if not yaml_path:
        cprint(Color.RED, "YAML file path cannot be empty.")
        _pause()
        return

    if not os.path.exists(yaml_path):
        cprint(Color.RED, f"YAML file not found: {yaml_path}")
        _pause()
        return

    if _input_yes_no("Edit the YAML file in vim before applying?", default=True):
        if not _ensure_vim_installed():
            _pause()
            return
        _open_in_vim(yaml_path)

    valid, err = _validate_yaml_syntax(yaml_path)
    if not valid:
        cprint(Color.RED, f"YAML syntax validation failed: {err}")
        _pause()
        return

    kubectl_valid, kubectl_err = _validate_with_kubectl(yaml_path)
    if not kubectl_valid:
        cprint(Color.RED, f"kubectl validation failed: {kubectl_err}")
        _pause()
        return

    result = subprocess.run(
        ["kubectl", "apply", "-f", yaml_path],
        capture_output=True,
        text=True
    )

    if result.returncode == 0:
        cprint(Color.GREEN, "Deployment YAML applied successfully.")
        if result.stdout.strip():
            print(result.stdout.strip())
    else:
        cprint(Color.RED, "Failed to apply deployment YAML.")
        if result.stderr.strip():
            print(result.stderr.strip())

    _pause()


def edit_deployment_menu():
    """
    Edit Deployment menu.
    """
    while True:
        print("\n--- Edit Deployment ---")
        print("1. Edit deployment directly with kubectl")
        print("2. Edit from YAML file")
        print("3. Back")
        choice = input("Choose (1-3): ").strip()

        if choice == "1":
            edit_deployment_direct()
        elif choice == "2":
            edit_deployment_yaml()
        elif choice == "3":
            break
        else:
            cprint(Color.RED, "Invalid option.")


def create_deployment_menu():
    """
    Create Deployment submenu.
    """
    while True:
        print("\n--- Create Deployment Options ---")
        print("Note: Quick Deploy probe support is currently basic and should be enhanced later.")
        print("1. Quick Deploy (Interactive Wizard)")
        print("2. Create YAML (Edit YAML file manually)")
        print("3. Back to Deployment Management")
        choice = input("Choose (1-3): ").strip()

        if choice == "1":
            quick_deploy_deployment()
        elif choice == "2":
            deployment_yaml_editor_mode()
        elif choice == "3":
            break
        else:
            cprint(Color.RED, "Invalid option.")


def deployment_menu():
    """
    Deployment main menu.
    """
    while True:
        print("\n--- Deployment Management ---")
        print("1. List Deployments")
        print("2. View Deployment Details")
        print("3. Create Deployment")
        print("4. Scale Replicas")
        print("5. Check Rollout Status")
        print("6. Edit Deployment")
        print("7. Export Deployment YAML")
        print("8. Delete Deployment")
        print("9. Back to Main Menu")
        choice = input("Choose (1-9): ").strip()

        if choice == "1":
            list_deployments()
        elif choice == "2":
            describe_deployment()
        elif choice == "3":
            create_deployment_menu()
        elif choice == "4":
            scale_deployment()
        elif choice == "5":
            rollout_status_deployment()
        elif choice == "6":
            edit_deployment_menu()
        elif choice == "7":
            export_deployment_menu()
        elif choice == "8":
            delete_deployment()
        elif choice == "9":
            break
        else:
            cprint(Color.RED, "Invalid option.")
