#!/usr/bin/env python3
"""
Common functions for resources (Pod, Deployment)
"""

from utils.color import cprint, Color
from utils.lang import t
from k8s.client import K8sClient, K8sClientError

client = K8sClient()


def get_pod_list_with_numbers():
    try:
        items = client.get_items("pods")
    except K8sClientError as e:
        return None, None, str(e)

    if not items:
        return [], {}, None

    pod_names = []
    pod_data = []

    for item in items:
        metadata = item.get("metadata", {})
        status = item.get("status", {})
        spec = item.get("spec", {})

        name = metadata.get("name", "")
        phase = status.get("phase", "")
        pod_ip = status.get("podIP", "")
        node_name = spec.get("nodeName", "")
        start_time = status.get("startTime", "")

        container_statuses = status.get("containerStatuses", [])
        total_containers = len(container_statuses)
        ready_containers = sum(1 for c in container_statuses if c.get("ready"))
        restart_count = sum(c.get("restartCount", 0) for c in container_statuses)

        ready = f"{ready_containers}/{total_containers}" if total_containers > 0 else "0/0"

        pod_names.append(name)
        pod_data.append({
            "name": name,
            "ready": ready,
            "status": phase,
            "restarts": str(restart_count),
            "age": start_time,
            "ip": pod_ip,
            "node": node_name
        })

    pod_map = {}
    numbered_list = []

    for idx, name in enumerate(pod_names, 1):
        pod_map[str(idx)] = name
        pod_map[name] = name
        numbered_list.append((idx, name, pod_data[idx - 1]))

    return numbered_list, pod_map, None


def get_deployment_list_with_numbers():
    try:
        items = client.get_items("deployments")
    except K8sClientError as e:
        return None, None, str(e)

    if not items:
        return [], {}, None

    dep_names = []
    dep_data = []

    for item in items:
        metadata = item.get("metadata", {})
        spec = item.get("spec", {})
        status = item.get("status", {})

        name = metadata.get("name", "")
        desired = spec.get("replicas", 0)
        ready_replicas = status.get("readyReplicas", 0)
        updated_replicas = status.get("updatedReplicas", 0)
        available_replicas = status.get("availableReplicas", 0)
        start_time = metadata.get("creationTimestamp", "")

        containers = spec.get("template", {}).get("spec", {}).get("containers", [])
        container_names = ",".join([c.get("name", "") for c in containers])
        image_names = ",".join([c.get("image", "") for c in containers])

        dep_names.append(name)
        dep_data.append({
            "name": name,
            "ready": f"{ready_replicas}/{desired}",
            "up_to_date": str(updated_replicas),
            "available": str(available_replicas),
            "age": start_time,
            "containers": container_names,
            "images": image_names
        })

    dep_map = {}
    numbered_list = []

    for idx, name in enumerate(dep_names, 1):
        dep_map[str(idx)] = name
        dep_map[name] = name
        numbered_list.append((idx, name, dep_data[idx - 1]))

    return numbered_list, dep_map, None


def get_deployment_replicaset_pod_info():
    try:
        rs_data = client.get_json("rs")
        pod_data = client.get_json("pods")
    except K8sClientError:
        return {}

    rs_pod_names = {}
    for item in pod_data.get("items", []):
        owner_refs = item.get("metadata", {}).get("ownerReferences", [])
        for ref in owner_refs:
            if ref.get("kind") == "ReplicaSet":
                rs_uid = ref.get("uid")
                if rs_uid not in rs_pod_names:
                    rs_pod_names[rs_uid] = []
                rs_pod_names[rs_uid].append(item.get("metadata", {}).get("name"))

    dep_to_rss = {}
    for item in rs_data.get("items", []):
        owner_refs = item.get("metadata", {}).get("ownerReferences", [])
        for ref in owner_refs:
            if ref.get("kind") == "Deployment":
                dep_uid = ref.get("uid")
                rs_name = item.get("metadata", {}).get("name")
                creation = item.get("metadata", {}).get("creationTimestamp", "")
                rs_uid = item.get("metadata", {}).get("uid")
                if dep_uid not in dep_to_rss:
                    dep_to_rss[dep_uid] = []
                dep_to_rss[dep_uid].append((creation, rs_name, rs_uid))

    dep_name_to_uid = {}
    for item in rs_data.get("items", []):
        for ref in item.get("metadata", {}).get("ownerReferences", []):
            if ref.get("kind") == "Deployment":
                dep_name = ref.get("name")
                dep_uid = ref.get("uid")
                dep_name_to_uid[dep_name] = dep_uid
                break

    result = {}
    for dep_uid, rs_list in dep_to_rss.items():
        if not rs_list:
            continue
        rs_list.sort(key=lambda x: x[0], reverse=True)
        newest_rs_name = rs_list[0][1]
        newest_rs_uid = rs_list[0][2]
        pod_names = rs_pod_names.get(newest_rs_uid, [])
        total = len(pod_names)
        display_names = pod_names[:3]
        pod_names_str = ", ".join(display_names)
        if total > 3:
            pod_names_str += f" ... (total {total})"
        for name, uid in dep_name_to_uid.items():
            if uid == dep_uid:
                result[name] = {
                    "replicaset": newest_rs_name,
                    "pod_names": pod_names_str,
                    "total_pods": total
                }
                break
    return result


def resolve_pod_identifier(identifier, pod_map):
    if identifier in pod_map:
        return pod_map[identifier]
    return None


def resolve_deployment_identifier(identifier, dep_map):
    if identifier in dep_map:
        return dep_map[identifier]
    return None
