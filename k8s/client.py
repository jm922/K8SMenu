#!/usr/bin/env python3
"""
Unified Kubernetes client wrapper
"""

import subprocess
import json
from typing import Any, Dict, List, Optional


class K8sClientError(Exception):
    """Raised when kubectl command fails."""
    pass


class K8sClient:
    def __init__(self, kubectl_bin: str = "kubectl", timeout: int = 20):
        self.kubectl_bin = kubectl_bin
        self.timeout = timeout

    def _run(self, args: List[str]) -> str:
        cmd = [self.kubectl_bin] + args
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=self.timeout
        )

        if result.returncode != 0:
            stderr = result.stderr.strip() or "Unknown kubectl error"
            raise K8sClientError(stderr)

        return result.stdout

    def get_json(
        self,
        resource: str,
        namespace: Optional[str] = None,
        extra_args: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        args = ["get", resource, "-o", "json"]
        if namespace:
            args.extend(["-n", namespace])
        if extra_args:
            args.extend(extra_args)

        output = self._run(args)
        return json.loads(output)

    def get_items(
        self,
        resource: str,
        namespace: Optional[str] = None,
        extra_args: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        data = self.get_json(resource, namespace=namespace, extra_args=extra_args)
        return data.get("items", [])

    def get_names(
        self,
        resource: str,
        namespace: Optional[str] = None
    ) -> List[str]:
        items = self.get_items(resource, namespace=namespace)
        return [item.get("metadata", {}).get("name", "") for item in items]
