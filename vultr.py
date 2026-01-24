"""
Vultr.com specific code
"""

import json
import os
import time
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional

from provider import BaseProvider
from ssh import run_ssh_script


class HttpError(RuntimeError):
    def __init__(self, message, response):
        super().__init__(message)
        self.response = response


class HttpResponse:
    def __init__(self, body, headers=None, status_code=200):
        self.status_code = status_code
        self.body = body
        self.headers = headers if headers is not None else {}

    def json(self):
        return json.loads(self.body)


class VultrApiClient:
    def __init__(self, access_token, requestor=None):
        self.endpoint = "https://api.vultr.com"

        self.access_token = access_token

        # Allow tests to inject a mocked requests client
        self.requestor = requestor if requestor else self._default_requestor

    def create_instance(self, params):
        self._api_request("POST", "/v2/instances", params)

    def delete_instance(self, instance_id):
        self._api_request("DELETE", f"/v2/instances/{instance_id}")

    def iterate_instances(self):
        base_url = "/v2/instances"
        url = base_url
        # I'm never going to have this many pages
        for _ in range(20):
            results = self._api_request("GET", url)
            data = results.json()
            for instance in data["instances"]:
                yield instance

            iter_token = data["meta"]["links"]["next"]
            if iter_token == "":
                break
            else:
                url = f"{base_url}?cursor={iter_token}"

    def _api_request(self, method, path, body=None, timeout=120):
        resp = self.requestor(
            method,
            f"{self.endpoint}{path}",
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            },
            json_data=body,
            timeout=timeout,
        )
        if resp.status_code < 200 or resp.status_code > 299:
            raise HttpError(f"Error response {resp.status_code}: {resp.body}", resp)

        return resp

    @staticmethod
    def _default_requestor(
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        json_data: Optional[Any] = None,
        raw_data: Optional[bytes] = None,
        timeout: int = 30,
    ) -> HttpResponse:
        if raw_data is not None:
            request_data = raw_data
        elif json_data is not None:
            request_data = json.dumps(json_data).encode()
        else:
            request_data = None

        try:
            response = urllib.request.urlopen(
                urllib.request.Request(
                    url,
                    method=method,
                    data=request_data,
                    headers=headers if headers is not None else {},
                ),
                timeout=timeout,
            )
        except urllib.error.HTTPError as e:
            response = e

        return HttpResponse(
            status_code=response.status,
            headers=dict(response.getheaders()),
            body=response.read(),
        )


class Provider(BaseProvider):
    def __init__(self, config, operating_system):
        self.operating_system = operating_system
        self.api_client = VultrApiClient(
            config.get("api_key", os.environ["VULTR_API_KEY"])
        )
        self.instance_region = config["instance_region"]
        self.instance_type = config["instance_type"]
        self.instance_os = config["instance_os"]
        self.ssh_key_id = config["ssh_key_id"]
        self.server_tag = config["server_tag"]

    def create_instance(self):
        self.api_client.create_instance(
            {
                "region": self.instance_region,
                "plan": self.instance_type,
                "os_id": self.instance_os,
                "sshkey_id": [self.ssh_key_id],
                "label": self.server_tag,
                "hostname": self.server_tag,
                "tags": [self.server_tag],
            }
        )

    def terminate_instance(self):
        maybe_instance = self._find_instance()
        if maybe_instance is None:
            raise AssertionError("Couldn't find matching server")
        instance_id = maybe_instance["id"]

        self.api_client.delete_instance(instance_id)

    def find_instance_ip(self):
        maybe_instance = self._find_instance()
        if maybe_instance is None:
            raise AssertionError("Couldn't find matching server")

        main_ip = maybe_instance["main_ip"]
        assert main_ip != "", "Instance doesn't have IP yet"
        return main_ip

    def find_instance_status(self):
        maybe_instance = self._find_instance()
        if maybe_instance is None:
            return "not_running"

        return maybe_instance["server_status"]

    def wait_for_instance(self):
        for _ in range(20):
            status = self.find_instance_status()
            if status == "ok":
                return

            time.sleep(5)

        raise AssertionError("Waited for 100 seconds but server wasn't ready")

    def _find_instance(self) -> Optional[dict]:
        for instance in self.api_client.iterate_instances():
            if self.server_tag in instance["tags"]:
                return instance

        return None

    def specific_setup(self, ip):
        if self.operating_system == "ubuntu":
            run_ssh_script(
                "root",
                ip,
                [
                    "useradd -m -G sudo -s /usr/bin/bash normal",
                    "cp -ar /root/.ssh /home/normal/.ssh",
                    "chown -R normal:normal /home/normal/.ssh",
                    "sed -i -e 's/^%sudo/# %sudo/' -e '$ a %sudo ALL = (ALL) NOPASSWD: ALL' /etc/sudoers",
                    "systemctl disable apparmor",
                    "reboot",
                ],
                expected_return_codes=(0, 255),
            )
        elif self.operating_system == "fedora":
            run_ssh_script(
                "root",
                ip,
                [
                    "useradd -m -G wheel normal",
                    "cp -ar /root/.ssh /home/normal/.ssh",
                    "chown -R normal:normal /home/normal/.ssh",
                    "sed -i -e 's/^%wheel/# %wheel/' -e '$ a %wheel ALL = (ALL) NOPASSWD: ALL' /etc/sudoers",
                    "sed -i 's/^net.ipv6/# net.ipv6/' /etc/sysctl.conf",
                ],
            )

    def get_username_for_ssh_check(self):
        return "root"
