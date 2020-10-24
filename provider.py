import time
import datetime
import subprocess

from ssh import run_ssh_result


class BaseProvider:
    def create_instance(self):
        raise NotImplementedError

    def terminate_instance(self):
        raise NotImplementedError

    def find_instance_ip(self):
        raise NotImplementedError

    def find_instance_status(self):
        raise NotImplementedError

    def wait_for_instance(self):
        pass

    def wait_for_ssh(self, ip, no_host_check=True):
        username = self.get_username_for_ssh_check()
        start = datetime.datetime.now()
        for _ in range(20):
            try:
                result = run_ssh_result(
                    username,
                    ip,
                    "true",
                    check=False,
                    no_host_check=no_host_check,
                    timeout=5
                )
                if result.returncode == 0:
                    return
            except subprocess.TimeoutExpired:
                pass

            time.sleep(5)

        end = datetime.datetime.now()
        td = end - start
        raise AssertionError(f"Couldn't connect via SSH after {td.seconds} seconds")

    def get_username_for_ssh_check(self):
        raise NotImplementedError

    def specific_setup(self, ip):
        pass
