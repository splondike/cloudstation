"""
SSH utilities
"""

import subprocess
import tempfile

from template import build_template


def run_ssh_script(username, remote_ip, lines, expected_return_codes=(0,), cleanup=False):
    fileno, filename = tempfile.mkstemp()
    with open(fileno, 'w') as fh:
        fh.write("#!/bin/bash\n")
        fh.write("set -xe\n")
        for line in lines:
            fh.write(line + "\n")
        fh.close()

    run_scp(username, remote_ip, filename, '/tmp/script.sh')

    result = run_ssh_result(
        username, remote_ip, 'bash', '/tmp/script.sh',
        capture_output=False,
        check=False
    )

    if cleanup:
        run_ssh_result(
            username, remote_ip, 'rm', '/tmp/script.sh'
        )

    if result.returncode not in expected_return_codes:
        raise RuntimeError(f"Script return code was {result.returncode}, expected {expected_return_codes}")


def run_ssh_result(username, remote_ip, *command, capture_output=True, check=True, no_host_check=False, **kwargs):
    ssh = ['ssh', '-o StrictHostKeyChecking=no'] if no_host_check else ['ssh']
    return subprocess.run(
        ssh + [
            f'{username}@{remote_ip}'
        ] + list(command),
        capture_output=capture_output,
        check=check,
        **kwargs
    )


def run_scp(username, remote_ip, local_file, remote_file):
    return subprocess.run(
        [
            'scp', local_file, f'{username}@{remote_ip}:{remote_file}'
        ],
        capture_output=True,
        check=True
    )


def run_scp_template(username, remote_ip, template_file, target_path, params={}):
    """
    Uses the files in templates and the variables in params to build a file,
    then copies it to target_path on the server.
    """

    fileno, filename = tempfile.mkstemp()
    with open(fileno, 'w') as fh:
        fh.write(build_template(template_file, params))

    return run_scp(username, remote_ip, filename, target_path)
