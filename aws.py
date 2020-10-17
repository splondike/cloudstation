"""
AWS Specific code
"""

import time
import subprocess


class Provider:
    def __init__(self, config):
        self.server_tag = config['server_tag']
        self.aws_cli_profile = config['aws_cli_profile']
        self.instance_type = config['instance_type']

    def find_instance_ip(self):
        rtn = subprocess.run(
            [
                'aws', '--profile', self.aws_cli_profile, 'ec2', 'describe-instances'
            ],
            capture_output=True,
            check=True
        )
        instance_ips = [
            instance["PublicIpAddress"]

            for reservation in json.loads(rtn.stdout)["Reservations"]
            for instance in reservation["Instances"]
            if instance["KeyName"] == self.server_tag
        ]

        if len(instance_ips) > 0:
            return instance_ips[0]
        else:
            return None

    def create_instance(self):
        subprocess.run(
            [
                'aws', '--profile', self.aws_cli_profile, 'ec2', 'run-instances', '--tag-specifications',
                '{"ResourceType":"instance","Tags":[{"Key":"owner","Value":"stefan-cloud-workstation"}]}',
                '--image-id', 'ami-06b1cc1d1e719ec37', '--count','1', '--instance-type',
                self.instance_type, '--key-name', self.server_tag, '--security-group-ids',
                'sg-03d2d037ac8eec952', '--ebs-optimized', '--block-device-mapping',
                '[ { \"DeviceName\": \"/dev/sda1\", \"Ebs\": { \"VolumeSize\": 120 } } ]'
            ],
            capture_output=True,
            check=True
        )

    def wait_for_instance(self):
        time.sleep(10)

    def specific_setup(self, ip):
        pass
