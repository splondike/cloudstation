"""
Vultr.com specific code
"""

import json
import time
from urllib.request import urlopen, Request
from urllib.parse import urlencode

from provider import BaseProvider
from ssh import run_ssh_script


class Provider(BaseProvider):
    def __init__(self, config):
        self.api_key = config['api_key']
        self.instance_region = config['instance_region']
        self.instance_type = config['instance_type']
        self.instance_os = config['instance_os']
        self.ssh_key_id = config['ssh_key_id']
        self.server_tag = config['server_tag']

    def create_instance(self):
        self._post(
            '/v1/server/create',
            {
                'DCID': self.instance_region,
                'VPSPLANID': self.instance_type,
                'OSID': self.instance_os,
                'SSHKEYID': self.ssh_key_id,
                'notify_activate': 'no',
                'label': self.server_tag,
                'hostname': self.server_tag,
                'tag': self.server_tag,
            }
        )

    def terminate_instance(self):
        instance_id = None
        for instance in self._get('/v1/server/list').values():
            if (instance['tag'] == self.server_tag) and (instance['status'] == 'active'):
                instance_id = instance['SUBID']

        if instance_id is None:
            raise AssertionError("Couldn't find matching server")

        self._post(
            '/v1/server/destroy',
            {
                'SUBID': instance_id
            },
            expect_json=False
        )

    def find_instance_ip(self):
        for instance in self._get('/v1/server/list').values():
            if (instance['tag'] == self.server_tag) and (instance['status'] == 'active'):
                return instance['main_ip']

        raise AssertionError("Couldn't find matching server")

    def find_instance_status(self):
        for instance in self._get('/v1/server/list').values():
            if (instance['tag'] == self.server_tag):
                return instance['status']

        return 'not_running'

    def wait_for_instance(self):
        for _ in range(10):
            for instance in self._get('/v1/server/list').values():
                if (instance['tag'] == self.server_tag) and (instance['status'] == 'active'):
                    return

            time.sleep(5)

        raise AssertionError("Waited for 50 seconds but server wasn't ready")

    def specific_setup(self, ip):
        run_ssh_script('root', ip, [
            "useradd -m -G wheel fedora",
            "cp -ar /root/.ssh /home/fedora/.ssh",
            "chown -R fedora:fedora /home/fedora/.ssh",
            "sed -i -e 's/^%wheel/# %wheel/' -e '$ a %wheel ALL = (ALL) NOPASSWD: ALL' /etc/sudoers",
            "sed -i 's/^net.ipv6/# net.ipv6/' /etc/sysctl.conf",
        ], cleanup=True)

    def get_username_for_ssh_check(self):
        return "root"

    def _post(self, path, data, expect_json=True):
        data_encoded = urlencode(data).encode('ascii')
        with urlopen(self._make_req(path), data_encoded) as f:
            if expect_json:
                return json.loads(f.read().decode('utf-8'))
            else:
                return f.read().decode('utf-8')

    def _get(self, path):
        with urlopen(self._make_req(path)) as f:
            return json.loads(f.read().decode('utf-8'))

    def _make_req(self, path):
        req = Request(f"https://api.vultr.com{path}")
        req.add_header('API-Key', self.api_key)
        return req
