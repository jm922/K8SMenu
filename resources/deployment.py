#!/usr/bin/env python3
"""
Deployment management functions
- Explicit English output
- Namespace-aware
- Show full kubectl command before execution
"""

import json
import os
import shlex
import subprocess
import tempfile
from datetime import datetime

import yaml

from utils.color import cprint, Color


CURRENT_NAMESPACE = "default"


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
    return creation_timestamp or ""


def _highlight(text):
    return f"{Color.BOLD}{Color.YELLOW}{text}{Color.END}"


def _hint(text, danger=False):
    color = Color.RED if danger else Color.CYAN
    return f"{color}({text}){Color.END}"


def _menu_line(number, label, hint_text=None, danger=False):
    if hint_text:
        print(f"{number}. {label} {_hint(hint_text, danger=danger)}")
    else:
        print(f"{number}. {label}")


def _title_with_ns(title):
    return f"--- {title} [{_highlight(f'NAMESPACE: {CURRENT_NAMESPACE}')} ] ---".replace(" }", "}")


def _print_command(cmd):
    print("\n" + "-" * 88)
    cprint(Color.BOLD + Color.YELLOW, "Executing command")
    cprint(Color.YELLOW, " ".join(shlex.quote(part) for part in cmd))
    print("-" * 88)


def _run_kubectl_text(args):
    cmd = ["kubectl"] + args
    _print_command(cmd)

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return None, (result.stderr or result.stdout).strip()

    return result.stdout, None


def _run_kubectl_json(args):
    cmd = ["kubectl"] + args + ["-o", "json"]
    _print_command(cmd)

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return None, (result.stderr or result.stdout).strip()

    try:
        return json.loads(result.stdout), None
    except Exception as e:
        return None, str(e)


def _ns_args():
    return ["-n", CURRENT_NAMESPACE]


def _list_namespaces():
    data, err = _run_kubectl_json(["get", "namespaces"])
    if err:
        return None, err

    names = []
    for item in data.get("items", []):
        name = item.get("metadata", {}).get("name", "")
        if name:
            names.append(name)

    return sorted(names), None


def _namespace_exists(name):
    _, err = _run_kubectl_json(["get", "namespace", name])
    return err is None


def _set_namespace():
    global CURRENT_NAMESPACE

    print("\n--- Set Deployment Namespace ---")
    print(f"Current namespace: {_highlight(CURRENT_NAMESPACE)}")

    namespaces, err = _list_namespaces()
    if err:
        cprint(Color.RED, f"Failed to list namespaces: {err}")
        if _input_yes_no("Do you want to enter namespace manually anyway?", default=False):
            namespace = _input_required("Enter namespace")
            if _namespace_exists(namespace):
                CURRENT_NAMESPACE = namespace
                cprint(Color.GREEN, f"Deployment namespace set to: {CURRENT_NAMESPACE}")
            else:
                cprint(Color.RED, f"Namespace not found: {namespace}")
        _pause()
        return

    if namespaces:
        print(f"\n{Color.BOLD}{Color.CYAN}Available Namespaces{Color.END}")
        print("-" * 50)
        for idx, name in enumerate(namespaces, 1):
            marker = " (current)" if name == CURRENT_NAMESPACE else ""
            display = _highlight(name) if name == CURRENT_NAMESPACE else name
            print(f"{Color.GREEN}{idx:<3}{Color.END} {display}{marker}")
    else:
        cprint(Color.YELLOW, "No namespaces found from kubectl output.")

    print("\nEnter a namespace number, namespace name, 'm' for manual input, or 'q' to cancel.")
    choice = input("Namespace selection: ").strip()

    if not choice or choice.lower() in ("q", "quit", "back"):
        cprint(Color.YELLOW, "Namespace change cancelled.")
        _pause()
        return

    selected_namespace = None

    if choice.lower() == "m":
        manual_name = _input_required("Enter namespace manually")
        if manual_name in namespaces or _namespace_exists(manual_name):
            selected_namespace = manual_name
        else:
            cprint(Color.RED, f"Namespace not found: {manual_name}")
            _pause()
            return
    elif choice.isdigit():
        idx = int(choice)
        if 1 <= idx <= len(namespaces):
            selected_namespace = namespaces[idx - 1]
        else:
            cprint(Color.RED, f"Invalid namespace number: {choice}")
            _pause()
            return
    else:
        if choice in namespaces or _namespace_exists(choice):
            selected_namespace = choice
        else:
            cprint(Color.RED, f"Namespace not found: {choice}")
            _pause()
            return

    CURRENT_NAMESPACE = selected_namespace
    cprint(Color.GREEN, f"Deployment namespace set to: {CURRENT_NAMESPACE}")
    _pause()


def _reset_namespace():
    global CURRENT_NAMESPACE
    CURRENT_NAMESPACE = "default"
    cprint(Color.GREEN, "Deployment namespace reset to: default")
    _pause()


def _get_current_revision(dep_json):
    return (
        dep_json.get("metadata", {})
        .get("annotations", {})
        .get("deployment.kubernetes.io/revision", "unknown")
    )


def _get_container_list(dep_json):
    return dep_json.get("spec", {}).get("template", {}).get("spec", {}).get("containers", [])


def _get_deployment_status_numbers(dep_json):
    spec = dep_json.get("spec", {})
    status = dep_json.get("status", {})
    return {
        "desired": spec.get("replicas", 0),
        "updated": status.get("updatedReplicas", 0),
        "ready": status.get("readyReplicas", 0),
        "available": status.get("availableReplicas", 0),
        "unavailable": status.get("unavailableReplicas", 0),
    }


def _is_fully_rolled_out(dep_json):
    numbers = _get_deployment_status_numbers(dep_json)
    desired = numbers["desired"]
    updated = numbers["updated"]
    ready = numbers["ready"]
    available = numbers["available"]
    unavailable = numbers["unavailable"]

    return (
        desired == updated
        and desired == ready
        and desired == available
        and unavailable == 0
    )


def _print_deployment_status(dep_name, dep_json, title="Current deployment status"):
    numbers = _get_deployment_status_numbers(dep_json)

    print(f"\n{Color.BOLD}{Color.CYAN}{title}{Color.END}")
    print(f"{Color.BLUE}Namespace:{Color.END}        {_highlight(CURRENT_NAMESPACE)}")
    print(f"{Color.BLUE}Deployment:{Color.END}       {dep_name}")
    print(f"{Color.BLUE}Desired replicas:{Color.END} {numbers['desired']}")
    print(f"{Color.BLUE}Updated replicas:{Color.END} {numbers['updated']}")
    print(f"{Color.BLUE}Ready replicas:{Color.END}   {numbers['ready']}")
    print(f"{Color.BLUE}Available:{Color.END}        {numbers['available']}")


def _apply_yaml_content(yaml_content):
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8") as f:
            f.write(yaml_content)
            tmp_path = f.name

        print("\nApplying configuration to cluster...")
        cmd = ["kubectl", "apply", "-f", tmp_path]
        _print_command(cmd)
        result = subprocess.run(cmd, capture_output=True, text=True)

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
    import shutil
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
    cmd = ["kubectl", "apply", "--dry-run=client", "-f", filepath]
    _print_command(cmd)
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0, (result.stderr or result.stdout).strip()


def list_deployments_with_numbers():
    print(f"\n--- Current Deployment List [{_highlight(f'NAMESPACE: {CURRENT_NAMESPACE}')} ] ---".replace(" }", "}"))

    data, err = _run_kubectl_json(["get", "deployments"] + _ns_args())
    if err:
        cprint(Color.RED, f"Failed to list deployments: {err}")
        return None

    items = data.get("items", [])
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


def _resolve_deployment_identifier(identifier, dep_map):
    return dep_map.get(identifier)


def show_deployment_pods(dep_name=None):
    if dep_name is None:
        result = list_deployments_with_numbers()
        if result is None:
            return

        numbered_list, dep_map = result
        if not numbered_list:
            cprint(Color.YELLOW, "No deployments found.")
            _pause()
            return

        print(f"\n{Color.BOLD}{Color.CYAN}Available Deployments{Color.END}")
        for idx, name, data in numbered_list:
            print(f"  {Color.GREEN}{idx}{Color.END}. {name} {_hint('Ready: ' + data['ready'])}")

        identifier = _input_required("Enter deployment number or name")
        dep_name = _resolve_deployment_identifier(identifier, dep_map)

        if not dep_name:
            cprint(Color.RED, f"Deployment not found: {identifier}")
            _pause()
            return

    dep_json, err = _run_kubectl_json(["get", "deployment", dep_name] + _ns_args())
    if err:
        cprint(Color.RED, f"Failed to get deployment details: {err}")
        _pause()
        return

    selector = dep_json.get("spec", {}).get("selector", {}).get("matchLabels", {})
    if not selector:
        selector = {"app": dep_name}

    label_selector = ",".join([f"{k}={v}" for k, v in selector.items()])

    pod_json, err = _run_kubectl_json(["get", "pods"] + _ns_args() + ["-l", label_selector])
    if err:
        cprint(Color.RED, f"Failed to get pods: {err}")
        _pause()
        return

    pod_items = pod_json.get("items", [])

    print(f"\nPods for Deployment '{dep_name}' [{_highlight(f'NAMESPACE: {CURRENT_NAMESPACE}')}, selector: {label_selector}]:")

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
    result = list_deployments_with_numbers()
    if result is None:
        return

    numbered_list, dep_map = result
    if not numbered_list:
        return

    print("\nEnter deployment number or name to show pods.")
    print("Press Enter to skip, or enter 'q' to quit this step.")
    identifier = input("Show pods for deployment: ").strip()

    if identifier == "":
        _pause()
        return

    if identifier.lower() in ["q", "quit"]:
        _pause()
        return

    dep_name = _resolve_deployment_identifier(identifier, dep_map)
    if dep_name:
        show_deployment_pods(dep_name)
        return

    cprint(Color.RED, f"Deployment not found: {identifier}")
    _pause()


def quick_deploy_deployment():
    print(f"\n{_title_with_ns('Create Deployment - Quick Deploy')}")

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
        key = _input_required("Environment variable name")
        value = _input_required("Environment variable value")
        env_vars.append({"name": key, "value": value})

    resources = None
    if _input_yes_no("Set resource limits?", default=False):
        cpu_req = input("CPU request (e.g. 100m) [default: 100m]: ").strip() or "100m"
        mem_req = input("Memory request (e.g. 128Mi) [default: 128Mi]: ").strip() or "128Mi"
        cpu_lim = input("CPU limit (e.g. 300m) [default: 300m]: ").strip() or "300m"
        mem_lim = input("Memory limit (e.g. 256Mi) [default: 256Mi]: ").strip() or "256Mi"

        resources = {
            "requests": {"cpu": cpu_req, "memory": mem_req},
            "limits": {"cpu": cpu_lim, "memory": mem_lim},
        }

    probes = {}

    if _input_yes_no("Enable readinessProbe?", default=False):
        path = input("HTTP path [default: /]: ").strip() or "/"
        probes["readinessProbe"] = {
            "httpGet": {"path": path, "port": port},
            "initialDelaySeconds": 5,
            "periodSeconds": 10,
        }

    if _input_yes_no("Enable livenessProbe?", default=False):
        path = input("HTTP path [default: /]: ").strip() or "/"
        probes["livenessProbe"] = {
            "httpGet": {"path": path, "port": port},
            "initialDelaySeconds": 10,
            "periodSeconds": 20,
        }

    container = {
        "name": name,
        "image": image,
        "imagePullPolicy": "IfNotPresent",
        "ports": [{"containerPort": port}],
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
            "namespace": CURRENT_NAMESPACE,
            "labels": {"app": name},
        },
        "spec": {
            "replicas": replicas,
            "selector": {"matchLabels": {"app": name}},
            "template": {
                "metadata": {"labels": {"app": name}},
                "spec": {"containers": [container]},
            },
        },
    }

    yaml_content = yaml.safe_dump(deployment, sort_keys=False)

    print("\nGenerated YAML:\n")
    print(yaml_content)

    _apply_yaml_content(yaml_content)
    _pause()


def generate_deployment_template():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"deployment_{timestamp}.yaml"
    template = f"""# Kubernetes Deployment YAML Template
# Edit this file to create your Deployment

apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-deployment
  namespace: {CURRENT_NAMESPACE}
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
"""
    return filename, template


def deployment_yaml_editor_mode():
    print(f"\n{_title_with_ns('Create Deployment - YAML Editor Mode')}")
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

    cmd = ["kubectl", "apply", "-f", filename]
    _print_command(cmd)
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        cprint(Color.GREEN, "Deployment applied successfully.")
        if result.stdout.strip():
            print(result.stdout.strip())
    else:
        cprint(Color.RED, "Failed to apply deployment.")
        if result.stderr.strip():
            print(result.stderr.strip())

    _pause()


def create_deployment_menu():
    while True:
        print(f"\n{_title_with_ns('Create Deployment Options')}")
        _menu_line("1", "Quick Deploy", "interactive wizard")
        _menu_line("2", "Create YAML", "manual edit")
        _menu_line("3", "Back", "return")
        choice = input("Choose (1-3): ").strip()

        if choice == "1":
            quick_deploy_deployment()
        elif choice == "2":
            deployment_yaml_editor_mode()
        elif choice == "3":
            break
        else:
            cprint(Color.RED, "Invalid option.")


def describe_deployment():
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
    dep_name = _resolve_deployment_identifier(identifier, dep_map)

    if not dep_name:
        cprint(Color.RED, f"Deployment not found: {identifier}")
        _pause()
        return

    print(f"Fetching details for deployment '{dep_name}'...")
    output, err = _run_kubectl_text(["describe", "deployment", dep_name] + _ns_args())

    if err:
        cprint(Color.RED, f"Failed to view deployment details: {dep_name}")
        print(err)
    else:
        print(output)

    _pause()


def scale_deployment():
    print(f"\n{_title_with_ns('Scale Deployment')}")

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
    dep_name = _resolve_deployment_identifier(identifier, dep_map)

    if not dep_name:
        cprint(Color.RED, f"Deployment not found: {identifier}")
        _pause()
        return

    dep_json, err = _run_kubectl_json(["get", "deployment", dep_name] + _ns_args())
    if err:
        cprint(Color.RED, f"Failed to get deployment details: {err}")
        _pause()
        return

    current_replicas = dep_json.get("spec", {}).get("replicas", 0)

    print(f"\n{Color.BOLD}{Color.CYAN}Current deployment{Color.END}")
    print(f"{Color.BLUE}Namespace:{Color.END}        {_highlight(CURRENT_NAMESPACE)}")
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

    scale_cmd = ["kubectl", "scale", "deployment", dep_name, f"--replicas={new_replicas}", "-n", CURRENT_NAMESPACE]

    print(f"\n{Color.BOLD}{Color.CYAN}Scale operation preview{Color.END}")
    print(f"{Color.BLUE}Namespace:{Color.END}        {_highlight(CURRENT_NAMESPACE)}")
    print(f"{Color.BLUE}Deployment:{Color.END}       {dep_name}")
    print(f"{Color.BLUE}Current replicas:{Color.END} {current_replicas}")
    print(f"{Color.BLUE}Target replicas:{Color.END}  {Color.YELLOW}{new_replicas}{Color.END}")
    print()
    print(f"{Color.BOLD}{Color.YELLOW}kubectl command:{Color.END}")
    print(f"{Color.YELLOW}{' '.join(shlex.quote(part) for part in scale_cmd)}{Color.END}")

    if not _input_yes_no("Proceed with scale operation?", default=True):
        cprint(Color.YELLOW, "Scale operation cancelled.")
        _pause()
        return

    _print_command(scale_cmd)
    result = subprocess.run(scale_cmd, capture_output=True, text=True)

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

    updated_json, err = _run_kubectl_json(["get", "deployment", dep_name] + _ns_args())
    if err:
        cprint(Color.YELLOW, f"Scaled, but failed to fetch updated deployment state: {err}")
        _pause()
        return

    _print_deployment_status(dep_name, updated_json, "Updated deployment status")

    if not _is_fully_rolled_out(updated_json):
        print()
        cprint(Color.YELLOW, "Scaling is still in progress. Final readiness may take a few more seconds.")

    _pause()


def update_deployment_image():
    print(f"\n{_title_with_ns('Update Deployment Image')}")

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
    dep_name = _resolve_deployment_identifier(identifier, dep_map)

    if not dep_name:
        cprint(Color.RED, f"Deployment not found: {identifier}")
        _pause()
        return

    dep_json, err = _run_kubectl_json(["get", "deployment", dep_name] + _ns_args())
    if err:
        cprint(Color.RED, f"Failed to get deployment details: {err}")
        _pause()
        return

    containers = _get_container_list(dep_json)
    if not containers:
        cprint(Color.RED, "No containers found in the selected Deployment.")
        _pause()
        return

    selected_container = None

    if len(containers) == 1:
        selected_container = containers[0]
        print(f"\n{Color.BOLD}{Color.CYAN}Current container{Color.END}")
        print(f"{Color.BLUE}Container:{Color.END} {selected_container.get('name', '')}")
        print(f"{Color.BLUE}Image:{Color.END}     {selected_container.get('image', '')}")
    else:
        print(f"\n{Color.BOLD}{Color.CYAN}Current containers{Color.END}")
        container_map = {}
        for idx, container in enumerate(containers, 1):
            cname = container.get("name", "")
            cimage = container.get("image", "")
            print(f"{Color.GREEN}{idx}.{Color.END} {cname:<20} {cimage}")
            container_map[str(idx)] = container
            container_map[cname] = container

        container_identifier = _input_required("Enter container number or name")
        selected_container = container_map.get(container_identifier)

        if not selected_container:
            cprint(Color.RED, f"Container not found: {container_identifier}")
            _pause()
            return

    container_name = selected_container.get("name", "")
    current_image = selected_container.get("image", "")

    print(f"\n{Color.BOLD}{Color.CYAN}Image update target{Color.END}")
    print(f"{Color.BLUE}Namespace:{Color.END}     {_highlight(CURRENT_NAMESPACE)}")
    print(f"{Color.BLUE}Deployment:{Color.END}    {dep_name}")
    print(f"{Color.BLUE}Container:{Color.END}     {container_name}")
    print(f"{Color.BLUE}Current image:{Color.END} {current_image}")

    new_image = _input_required("Enter new image")

    if new_image == current_image:
        cprint(Color.YELLOW, f"Image is already set to {current_image}. No changes applied.")
        _pause()
        return

    update_cmd = [
        "kubectl", "set", "image",
        f"deployment/{dep_name}",
        f"{container_name}={new_image}",
        "-n", CURRENT_NAMESPACE
    ]

    print(f"\n{Color.BOLD}{Color.CYAN}Image update preview{Color.END}")
    print(f"{Color.BLUE}Namespace:{Color.END}     {_highlight(CURRENT_NAMESPACE)}")
    print(f"{Color.BLUE}Deployment:{Color.END}    {dep_name}")
    print(f"{Color.BLUE}Container:{Color.END}     {container_name}")
    print(f"{Color.BLUE}Current image:{Color.END} {current_image}")
    print(f"{Color.BLUE}Target image:{Color.END}  {Color.YELLOW}{new_image}{Color.END}")
    print()
    print(f"{Color.BOLD}{Color.YELLOW}kubectl command:{Color.END}")
    print(f"{Color.YELLOW}{' '.join(shlex.quote(part) for part in update_cmd)}{Color.END}")

    if not _input_yes_no("Proceed with image update?", default=True):
        cprint(Color.YELLOW, "Image update cancelled.")
        _pause()
        return

    _print_command(update_cmd)
    result = subprocess.run(update_cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print()
        cprint(Color.RED, "Failed to update deployment image.")
        if result.stderr.strip():
            print(f"{Color.RED}{result.stderr.strip()}{Color.END}")
        elif result.stdout.strip():
            print(f"{Color.RED}{result.stdout.strip()}{Color.END}")
        _pause()
        return

    print()
    cprint(Color.GREEN, "Image update command applied successfully.")

    if result.stdout.strip():
        print(f"{Color.BOLD}{Color.GREEN}kubectl output:{Color.END}")
        print(f"{Color.GREEN}{result.stdout.strip()}{Color.END}")

    updated_json, err = _run_kubectl_json(["get", "deployment", dep_name] + _ns_args())
    if err:
        cprint(Color.YELLOW, f"Image updated, but failed to fetch updated deployment state: {err}")
        _pause()
        return

    updated_containers = _get_container_list(updated_json)
    updated_image = new_image
    for container in updated_containers:
        if container.get("name") == container_name:
            updated_image = container.get("image", new_image)
            break

    numbers = _get_deployment_status_numbers(updated_json)

    print(f"\n{Color.BOLD}{Color.CYAN}Updated deployment status{Color.END}")
    print(f"{Color.BLUE}Namespace:{Color.END}        {_highlight(CURRENT_NAMESPACE)}")
    print(f"{Color.BLUE}Deployment:{Color.END}       {dep_name}")
    print(f"{Color.BLUE}Container:{Color.END}        {container_name}")
    print(f"{Color.BLUE}Previous image:{Color.END}   {current_image}")
    print(f"{Color.BLUE}Current image:{Color.END}    {updated_image}")
    print(f"{Color.BLUE}Desired replicas:{Color.END} {numbers['desired']}")
    print(f"{Color.BLUE}Updated replicas:{Color.END} {numbers['updated']}")
    print(f"{Color.BLUE}Ready replicas:{Color.END}   {numbers['ready']}")
    print(f"{Color.BLUE}Available:{Color.END}        {numbers['available']}")

    print()
    cprint(Color.YELLOW, "Image update was accepted. Rollout may still be in progress.")
    cprint(Color.YELLOW, "Use 'Check Rollout Status' to monitor completion.")

    _pause()


def rollout_status_deployment():
    print(f"\n{_title_with_ns('Rollout Status')}")

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
    dep_name = _resolve_deployment_identifier(identifier, dep_map)

    if not dep_name:
        cprint(Color.RED, f"Deployment not found: {identifier}")
        _pause()
        return

    timeout = _input_default("Enter rollout timeout", "180s")

    rollout_cmd = [
        "kubectl", "rollout", "status",
        f"deployment/{dep_name}",
        f"--timeout={timeout}",
        "-n", CURRENT_NAMESPACE
    ]

    print(f"\n{Color.BOLD}{Color.CYAN}Rollout status preview{Color.END}")
    print(f"{Color.BLUE}Namespace:{Color.END}  {_highlight(CURRENT_NAMESPACE)}")
    print(f"{Color.BLUE}Deployment:{Color.END} {dep_name}")
    print(f"{Color.BLUE}Timeout:{Color.END}    {Color.YELLOW}{timeout}{Color.END}")
    print()
    print(f"{Color.BOLD}{Color.YELLOW}kubectl command:{Color.END}")
    print(f"{Color.YELLOW}{' '.join(shlex.quote(part) for part in rollout_cmd)}{Color.END}")

    if not _input_yes_no("Proceed with rollout status check?", default=True):
        cprint(Color.YELLOW, "Rollout status check cancelled.")
        _pause()
        return

    print()
    cprint(Color.CYAN, "Checking rollout status...")
    _print_command(rollout_cmd)
    result = subprocess.run(rollout_cmd, capture_output=True, text=True)

    print()
    raw_output = (result.stderr or result.stdout or "").strip()

    dep_json, err = _run_kubectl_json(["get", "deployment", dep_name] + _ns_args())
    if err:
        if result.returncode == 0:
            cprint(Color.GREEN, "Rollout status completed successfully.")
            if result.stdout.strip():
                print(f"{Color.BOLD}{Color.GREEN}kubectl output:{Color.END}")
                print(f"{Color.GREEN}{result.stdout.strip()}{Color.END}")
        else:
            cprint(Color.RED, "Rollout status check failed or timed out.")
            if raw_output:
                print(f"{Color.RED}{raw_output}{Color.END}")

        cprint(Color.YELLOW, f"Failed to fetch deployment details after rollout check: {err}")
        _pause()
        return

    fully_rolled_out = _is_fully_rolled_out(dep_json)

    if result.returncode == 0:
        cprint(Color.GREEN, "Rollout status completed successfully.")
        if result.stdout.strip():
            print(f"{Color.BOLD}{Color.GREEN}kubectl output:{Color.END}")
            print(f"{Color.GREEN}{result.stdout.strip()}{Color.END}")
    else:
        if fully_rolled_out:
            cprint(Color.YELLOW, "Rollout status command timed out, but the Deployment now appears fully rolled out.")
            if raw_output:
                print(f"{Color.YELLOW}{raw_output}{Color.END}")
        else:
            cprint(Color.RED, "Rollout status check failed or timed out.")
            if raw_output:
                print(f"{Color.RED}{raw_output}{Color.END}")

    _print_deployment_status(dep_name, dep_json, "Current deployment status")

    if result.returncode != 0 and not fully_rolled_out:
        print()
        cprint(Color.YELLOW, "The Deployment does not appear fully rolled out yet.")
        cprint(Color.YELLOW, "You may need more time, or there may be an actual rollout problem.")

    _pause()


def view_rollout_history():
    print(f"\n{_title_with_ns('View Rollout History')}")

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
    dep_name = _resolve_deployment_identifier(identifier, dep_map)

    if not dep_name:
        cprint(Color.RED, f"Deployment not found: {identifier}")
        _pause()
        return

    dep_json, err = _run_kubectl_json(["get", "deployment", dep_name] + _ns_args())
    if err:
        cprint(Color.RED, f"Failed to get deployment details: {err}")
        _pause()
        return

    current_revision = _get_current_revision(dep_json)
    containers = _get_container_list(dep_json)
    image_summary = ", ".join([f"{c.get('name', '')}={c.get('image', '')}" for c in containers])

    print(f"\n{Color.BOLD}{Color.CYAN}Current deployment state{Color.END}")
    print(f"{Color.BLUE}Namespace:{Color.END}  {_highlight(CURRENT_NAMESPACE)}")
    print(f"{Color.BLUE}Deployment:{Color.END} {dep_name}")
    print(f"{Color.BLUE}Revision:{Color.END}   {current_revision}")
    print(f"{Color.BLUE}Images:{Color.END}     {image_summary or 'N/A'}")

    history_cmd = ["kubectl", "rollout", "history", f"deployment/{dep_name}", "-n", CURRENT_NAMESPACE]

    print(f"\n{Color.BOLD}{Color.CYAN}Rollout history preview{Color.END}")
    print(f"{Color.BLUE}Namespace:{Color.END}  {_highlight(CURRENT_NAMESPACE)}")
    print(f"{Color.BLUE}Deployment:{Color.END} {dep_name}")
    print()
    print(f"{Color.BOLD}{Color.YELLOW}kubectl command:{Color.END}")
    print(f"{Color.YELLOW}{' '.join(shlex.quote(part) for part in history_cmd)}{Color.END}")

    if not _input_yes_no("Proceed with rollout history check?", default=True):
        cprint(Color.YELLOW, "Rollout history check cancelled.")
        _pause()
        return

    print()
    cprint(Color.CYAN, "Checking rollout history...")
    _print_command(history_cmd)
    result = subprocess.run(history_cmd, capture_output=True, text=True)

    print()

    if result.returncode == 0:
        cprint(Color.GREEN, "Rollout history retrieved successfully.")
        if result.stdout.strip():
            print(f"{Color.BOLD}{Color.GREEN}kubectl output:{Color.END}")
            print(result.stdout.strip())
    else:
        cprint(Color.RED, "Failed to get rollout history.")
        if result.stderr.strip():
            print(f"{Color.RED}{result.stderr.strip()}{Color.END}")
        elif result.stdout.strip():
            print(f"{Color.RED}{result.stdout.strip()}{Color.END}")

    _pause()


def view_revision_details():
    print(f"\n{_title_with_ns('View Revision Details')}")

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
    dep_name = _resolve_deployment_identifier(identifier, dep_map)

    if not dep_name:
        cprint(Color.RED, f"Deployment not found: {identifier}")
        _pause()
        return

    dep_json, err = _run_kubectl_json(["get", "deployment", dep_name] + _ns_args())
    if err:
        cprint(Color.RED, f"Failed to get deployment details: {err}")
        _pause()
        return

    current_revision = _get_current_revision(dep_json)
    containers = _get_container_list(dep_json)
    image_summary = ", ".join([f"{c.get('name', '')}={c.get('image', '')}" for c in containers])

    print(f"\n{Color.BOLD}{Color.CYAN}Current deployment state{Color.END}")
    print(f"{Color.BLUE}Namespace:{Color.END}        {_highlight(CURRENT_NAMESPACE)}")
    print(f"{Color.BLUE}Deployment:{Color.END}       {dep_name}")
    print(f"{Color.BLUE}Current revision:{Color.END} {current_revision}")
    print(f"{Color.BLUE}Images:{Color.END}           {image_summary or 'N/A'}")

    revision = _input_required("Enter revision number")

    if not revision.isdigit():
        cprint(Color.RED, "Revision must be a positive integer.")
        _pause()
        return

    revision_cmd = [
        "kubectl", "rollout", "history",
        f"deployment/{dep_name}",
        f"--revision={revision}",
        "-n", CURRENT_NAMESPACE
    ]

    print(f"\n{Color.BOLD}{Color.CYAN}Revision details preview{Color.END}")
    print(f"{Color.BLUE}Namespace:{Color.END}  {_highlight(CURRENT_NAMESPACE)}")
    print(f"{Color.BLUE}Deployment:{Color.END} {dep_name}")
    print(f"{Color.BLUE}Revision:{Color.END}   {revision}")
    print()
    print(f"{Color.BOLD}{Color.YELLOW}kubectl command:{Color.END}")
    print(f"{Color.YELLOW}{' '.join(shlex.quote(part) for part in revision_cmd)}{Color.END}")

    if not _input_yes_no("Proceed with revision details check?", default=True):
        cprint(Color.YELLOW, "Revision details check cancelled.")
        _pause()
        return

    print()
    cprint(Color.CYAN, "Checking revision details...")
    _print_command(revision_cmd)
    result = subprocess.run(revision_cmd, capture_output=True, text=True)

    print()

    if result.returncode == 0:
        cprint(Color.GREEN, "Revision details retrieved successfully.")
        if result.stdout.strip():
            print(f"{Color.BOLD}{Color.GREEN}kubectl output:{Color.END}")
            print(result.stdout.strip())
    else:
        cprint(Color.RED, "Failed to get revision details.")
        if result.stderr.strip():
            print(f"{Color.RED}{result.stderr.strip()}{Color.END}")
        elif result.stdout.strip():
            print(f"{Color.RED}{result.stdout.strip()}{Color.END}")

    _pause()


def rollback_deployment():
    print(f"\n{_title_with_ns('Roll Back Deployment')}")

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
    dep_name = _resolve_deployment_identifier(identifier, dep_map)

    if not dep_name:
        cprint(Color.RED, f"Deployment not found: {identifier}")
        _pause()
        return

    dep_json, err = _run_kubectl_json(["get", "deployment", dep_name] + _ns_args())
    if err:
        cprint(Color.RED, f"Failed to get deployment details: {err}")
        _pause()
        return

    current_revision = _get_current_revision(dep_json)
    containers = _get_container_list(dep_json)
    image_summary = ", ".join([f"{c.get('name', '')}={c.get('image', '')}" for c in containers])

    print(f"\n{Color.BOLD}{Color.CYAN}Current deployment state{Color.END}")
    print(f"{Color.BLUE}Namespace:{Color.END}  {_highlight(CURRENT_NAMESPACE)}")
    print(f"{Color.BLUE}Deployment:{Color.END} {dep_name}")
    print(f"{Color.BLUE}Revision:{Color.END}   {current_revision}")
    print(f"{Color.BLUE}Images:{Color.END}     {image_summary or 'N/A'}")

    rollback_cmd = ["kubectl", "rollout", "undo", f"deployment/{dep_name}", "-n", CURRENT_NAMESPACE]

    print(f"\n{Color.BOLD}{Color.CYAN}Rollback preview{Color.END}")
    print(f"{Color.BLUE}Namespace:{Color.END}  {_highlight(CURRENT_NAMESPACE)}")
    print(f"{Color.BLUE}Deployment:{Color.END} {dep_name}")
    print(f"{Color.BLUE}Revision:{Color.END}   {current_revision}")
    print()
    print(f"{Color.BOLD}{Color.YELLOW}kubectl command:{Color.END}")
    print(f"{Color.YELLOW}{' '.join(shlex.quote(part) for part in rollback_cmd)}{Color.END}")

    if not _input_yes_no("Proceed with rollback?", default=True):
        cprint(Color.YELLOW, "Rollback cancelled.")
        _pause()
        return

    _print_command(rollback_cmd)
    result = subprocess.run(rollback_cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print()
        cprint(Color.RED, "Failed to roll back deployment.")
        if result.stderr.strip():
            print(f"{Color.RED}{result.stderr.strip()}{Color.END}")
        elif result.stdout.strip():
            print(f"{Color.RED}{result.stdout.strip()}{Color.END}")
        _pause()
        return

    print()
    cprint(Color.GREEN, "Rollback command applied successfully.")

    if result.stdout.strip():
        print(f"{Color.BOLD}{Color.GREEN}kubectl output:{Color.END}")
        print(f"{Color.GREEN}{result.stdout.strip()}{Color.END}")

    updated_json, err = _run_kubectl_json(["get", "deployment", dep_name] + _ns_args())
    if err:
        cprint(Color.YELLOW, f"Rollback applied, but failed to fetch updated deployment state: {err}")
        _pause()
        return

    new_revision = _get_current_revision(updated_json)
    updated_containers = _get_container_list(updated_json)
    updated_image_summary = ", ".join([f"{c.get('name', '')}={c.get('image', '')}" for c in updated_containers])

    numbers = _get_deployment_status_numbers(updated_json)

    print(f"\n{Color.BOLD}{Color.CYAN}Updated deployment status{Color.END}")
    print(f"{Color.BLUE}Namespace:{Color.END}         {_highlight(CURRENT_NAMESPACE)}")
    print(f"{Color.BLUE}Deployment:{Color.END}        {dep_name}")
    print(f"{Color.BLUE}Previous revision:{Color.END} {current_revision}")
    print(f"{Color.BLUE}Current revision:{Color.END}  {new_revision}")
    print(f"{Color.BLUE}Images:{Color.END}            {updated_image_summary or 'N/A'}")
    print(f"{Color.BLUE}Desired replicas:{Color.END}  {numbers['desired']}")
    print(f"{Color.BLUE}Updated replicas:{Color.END}  {numbers['updated']}")
    print(f"{Color.BLUE}Ready replicas:{Color.END}    {numbers['ready']}")
    print(f"{Color.BLUE}Available:{Color.END}         {numbers['available']}")

    print()
    cprint(Color.YELLOW, "Rollback was accepted. Rollout may still be in progress.")
    cprint(Color.YELLOW, "Use 'Check Rollout Status' to monitor completion.")

    _pause()


def show_deployment_yaml():
    result = list_deployments_with_numbers()
    if result is None:
        cprint(Color.YELLOW, "No deployments available.")
        return

    numbered_list, dep_map = result
    if not numbered_list:
        cprint(Color.YELLOW, "No deployments available.")
        return

    identifier = _input_required("Enter deployment number or name to display YAML")
    dep_name = _resolve_deployment_identifier(identifier, dep_map)

    if not dep_name:
        cprint(Color.RED, f"Deployment not found: {identifier}")
        _pause()
        return

    output, err = _run_kubectl_text(["get", "deployment", dep_name] + _ns_args() + ["-o", "yaml"])

    if err:
        cprint(Color.RED, f"Failed to export YAML for deployment: {dep_name}")
        print(err)
    else:
        print("\nDeployment YAML:\n")
        print(output)

    _pause()


def save_deployment_yaml():
    result = list_deployments_with_numbers()
    if result is None:
        cprint(Color.YELLOW, "No deployments available.")
        return

    numbered_list, dep_map = result
    if not numbered_list:
        cprint(Color.YELLOW, "No deployments available.")
        return

    identifier = _input_required("Enter deployment number or name to save YAML")
    dep_name = _resolve_deployment_identifier(identifier, dep_map)

    if not dep_name:
        cprint(Color.RED, f"Deployment not found: {identifier}")
        _pause()
        return

    filename = f"deployment_{CURRENT_NAMESPACE}_{dep_name}.yaml"
    if os.path.exists(filename):
        if not _input_yes_no(f"File '{filename}' already exists. Overwrite?", default=False):
            cprint(Color.YELLOW, "Save cancelled.")
            _pause()
            return

    output, err = _run_kubectl_text(["get", "deployment", dep_name] + _ns_args() + ["-o", "yaml"])

    if err:
        cprint(Color.RED, f"Failed to export YAML for deployment: {dep_name}")
        print(err)
        _pause()
        return

    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write(output)
        cprint(Color.GREEN, f"YAML saved successfully: {filename}")
    except Exception as e:
        cprint(Color.RED, f"Failed to save YAML file: {e}")

    _pause()


def export_deployment_menu():
    while True:
        print(f"\n{_title_with_ns('Export Deployment YAML')}")
        _menu_line("1", "Show Deployment YAML", "print to screen")
        _menu_line("2", "Save Deployment YAML to file", "local file")
        _menu_line("3", "Back", "return")
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

        dep_name = _resolve_deployment_identifier(identifier, dep_map)
        if not dep_name:
            cprint(Color.RED, f"Deployment not found: {identifier}")
            continue

        cmd = ["kubectl", "edit", "deployment", dep_name, "-n", CURRENT_NAMESPACE]
        cprint(Color.BLUE, f"Opening deployment '{dep_name}' in kubectl edit...")
        _print_command(cmd)
        result = subprocess.run(cmd)

        if result.returncode == 0:
            cprint(Color.GREEN, "Deployment edited successfully.")
        else:
            cprint(Color.RED, "Failed to edit deployment.")

        _pause()
        return


def edit_deployment_yaml():
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
    dep_name = _resolve_deployment_identifier(identifier, dep_map)

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

    cmd = ["kubectl", "apply", "-f", yaml_path]
    _print_command(cmd)
    result = subprocess.run(cmd, capture_output=True, text=True)

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
    while True:
        print(f"\n{_title_with_ns('Edit Deployment')}")
        _menu_line("1", "Edit deployment directly with kubectl", "live edit")
        _menu_line("2", "Edit from YAML file", "apply file")
        _menu_line("3", "Back", "return")
        choice = input("Choose (1-3): ").strip()

        if choice == "1":
            edit_deployment_direct()
        elif choice == "2":
            edit_deployment_yaml()
        elif choice == "3":
            break
        else:
            cprint(Color.RED, "Invalid option.")


def delete_deployment():
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
            dep_name = _resolve_deployment_identifier(identifier, dep_map)
            if dep_name:
                deps_to_delete.append(dep_name)
            else:
                cprint(Color.RED, f"Deployment not found: {identifier}")
                continue

        if not deps_to_delete:
            cprint(Color.YELLOW, "No valid deployments selected.")
            continue

        print(f"\nSelected Deployments [{_highlight(f'NAMESPACE: {CURRENT_NAMESPACE}')}]")
        for dep in deps_to_delete:
            print(f"  - {dep}")

        if _input_yes_no("Confirm deletion?", default=False):
            success = 0
            failed = 0

            for dep in deps_to_delete:
                cmd = ["kubectl", "delete", "deployment", dep, "-n", CURRENT_NAMESPACE]
                _print_command(cmd)
                result = subprocess.run(cmd, capture_output=True, text=True)
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


def deployment_menu():
    while True:
        print(f"\n{_title_with_ns('Deployment Management')}")
        _menu_line("1", "List Deployments", "overview")
        _menu_line("2", "View Deployment Details", "kubectl describe")
        _menu_line("3", "Create Deployment", "quick deploy / YAML")
        _menu_line("4", "Scale Replicas", "change replica count")
        _menu_line("5", "Update Deployment Image", "set image")
        _menu_line("6", "Check Rollout Status", "monitor progress")
        _menu_line("7", "View Rollout History", "revision list")
        _menu_line("8", "View Revision Details", "specific revision")
        _menu_line("9", "Roll Back Deployment", "previous revision")
        _menu_line("10", "Edit Deployment", "live / YAML")
        _menu_line("11", "Export Deployment YAML", "show / save")
        _menu_line("12", "Delete Deployment", "dangerous", danger=True)
        _menu_line("13", "Set Namespace", "list or manual input")
        _menu_line("14", "Reset Namespace to default")
        _menu_line("15", "Back to Main Menu", "return")
        choice = input("Choose (1-15): ").strip()

        if choice == "1":
            list_deployments()
        elif choice == "2":
            describe_deployment()
        elif choice == "3":
            create_deployment_menu()
        elif choice == "4":
            scale_deployment()
        elif choice == "5":
            update_deployment_image()
        elif choice == "6":
            rollout_status_deployment()
        elif choice == "7":
            view_rollout_history()
        elif choice == "8":
            view_revision_details()
        elif choice == "9":
            rollback_deployment()
        elif choice == "10":
            edit_deployment_menu()
        elif choice == "11":
            export_deployment_menu()
        elif choice == "12":
            delete_deployment()
        elif choice == "13":
            _set_namespace()
        elif choice == "14":
            _reset_namespace()
        elif choice == "15":
            break
        else:
            cprint(Color.RED, "Invalid option.")
