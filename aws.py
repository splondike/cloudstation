"""
AWS Specific code
"""

import json
import subprocess
import time

from provider import BaseProvider
from ssh import run_ssh_script


class Provider(BaseProvider):
    def __init__(self, config):
        self.server_tag = config['server_tag']
        self.aws_cli_profile = config['aws_cli_profile']
        self.instance_type = config['instance_type']
        self.security_group_id = config['security_group_id']
        self.image_id = config['image_id']
        self.volume_size_gb = config['volume_size_gb']
        self.ssh_key_id = config['ssh_key_id']

    def create_instance(self):
        subprocess.run(
            [
                'aws', '--profile', self.aws_cli_profile, 'ec2', 'run-instances',
                '--tag-specifications', '{"ResourceType":"instance","Tags":[{"Key":"owner","Value":"%s"}]}'  % self.server_tag,
                '--image-id', self.image_id, '--count', '1', '--instance-type',
                self.instance_type, '--key-name', self.ssh_key_id, '--security-group-ids',
                self.security_group_id, '--ebs-optimized', '--block-device-mapping',
                '[ { \"DeviceName\": \"/dev/sda1\", \"Ebs\": { \"VolumeSize\": %s } } ]' % self.volume_size_gb
            ],
            capture_output=True,
            check=True
        )

    def terminate_instance(self):
        instance = self._find_matching_instances()[0]
        rtn = subprocess.run(
            [
                'aws', '--profile', self.aws_cli_profile, 'ec2', 'terminate-instances',
                '--instance-ids', instance['InstanceId']
            ],
            capture_output=True,
            check=True
        )

    def find_instance_ip(self):
        instance_ips = [
            instance['PublicIpAddress']

            for instance in self._find_matching_instances()
        ]

        if len(instance_ips) > 0:
            return instance_ips[0]
        else:
            raise AssertionError("Couldn't find matching server")

    def find_instance_status(self):
        instance_statuses = [
            instance['State']['Name']

            for instance in self._find_matching_instances()
        ]

        if len(instance_statuses) > 0:
            return instance_statuses[0]
        else:
            return 'not_running'

    def wait_for_instance(self):
        # The instance transitions quite quickly to having an IP,
        # so I think this is fine
        time.sleep(10)

    def get_username_for_ssh_check(self):
        return 'fedora'

    def specific_setup(self, ip):
        run_ssh_script('fedora', ip, [
            "sudo dnf update -y",
            "sudo dnf install -y policycoreutils-python-utils firewalld",
            "sudo systemctl enable firewalld",
            "sudo reboot"
        ], cleanup=False, expected_return_codes=(0, 255))

    def _find_matching_instances(self):
        data = self._run_describe_instances()
        return [
            instance

            for reservation in data['Reservations']
            for instance in reservation['Instances']
            if self.server_tag in [tag['Value'] for tag in instance['Tags']]
            # These ones hang around for some time not doing anything
            if instance['State']['Name'] != 'terminated'
        ]

    def _run_describe_instances(self):
        rtn = subprocess.run(
            [
                'aws', '--profile', self.aws_cli_profile, 'ec2', 'describe-instances'
            ],
            capture_output=True,
            check=True
        )
        return json.loads(rtn.stdout)
