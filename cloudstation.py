#!/usr/bin/env python

"""
Script to set up a linux cloud workstation linked to my local environment via a Wireguard VPN
"""

import os
import sys
import time
import json
import logging
import configparser
import subprocess

from ssh import run_scp_template, run_ssh_script, run_ssh_result
from template import build_template

logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)


def run_remote_wireguard_setup(username, remote_ip, wireguard_pk, operating_system):
    """
    Sets up a wireguard connection to the server and have an rsync daemon running
    pointing to the /home/.../code/ directory.
    """

    server_keys = generate_wireguard_keys()
    # Copy up the config files we'll need
    run_scp_template(
        username,
        remote_ip,
        (
            "wireguard-server-ubuntu.conf"
            if operating_system == "ubuntu"
            else "wireguard-server-fedora.conf"
        ),
        "/tmp/wireguard-server.conf",
        params={
            "server_privatekey": server_keys["private_key"],
            "client_publickey": wireguard_pk,
        },
    )
    run_scp_template(username, remote_ip, "rsyncd.conf", "/tmp/rsyncd.conf")
    run_scp_template(username, remote_ip, "wireguard.service", "/tmp/wireguard.service")
    run_scp_template(username, remote_ip, "rsyncd.service", "/tmp/rsyncd.service")

    if operating_system == "ubuntu":
        os_steps = [
            "sudo apt install wireguard-tools",
        ]
    elif operating_system == "fedora":
        os_steps = [
            "sudo dnf install -y wireguard-tools rsync-daemon",
            # Allow rsync running as normal user via systemd to access everything and bind to
            # the ports it needs to
            "sudo setsebool -P rsync_full_access=true",
            "sudo semanage port -a -t rsync_port_t -p tcp 12000",
        ]

    # Install the files and get the daemons running
    run_ssh_script(
        username,
        remote_ip,
        os_steps
        + [
            "sudo install -o root -g root -m 600 -Z /tmp/wireguard-server.conf /etc/wireguard/wg0.conf",
            "sudo install -o root -g root -m 644 -Z /tmp/rsyncd.conf /etc/rsyncd.conf",
            "sudo install -o root -g root -m 644 -Z /tmp/wireguard.service /etc/systemd/system/",
            "sudo install -o root -g root -m 644 -Z /tmp/rsyncd.service /etc/systemd/system/",
            "sudo systemctl enable wireguard",
            "sudo systemctl enable rsyncd",
            "sudo systemctl start wireguard",
            "sudo systemctl start rsyncd",
            "mkdir ~/code/",
        ],
    )

    return server_keys["public_key"]


def generate_wireguard_keys():
    """
    Generates a private and public wireguard key
    """

    private_result = subprocess.run(["wg", "genkey"], capture_output=True, check=True)
    private_key = private_result.stdout.strip()
    public_result = subprocess.run(
        ["wg", "pubkey"], input=private_key, capture_output=True, check=True
    )
    public_key = public_result.stdout.strip()

    return {
        "private_key": private_key.decode("utf8"),
        "public_key": public_key.decode("utf8"),
    }


def set_up_wireguard(remote_ip, client_keys, server_wireguard_public_key):
    conf_path = os.environ["HOME"] + "/Desktop/wg0.conf"
    with open(conf_path, "w") as fh:
        fh.write(
            build_template(
                "wireguard-client.conf",
                params={
                    "client_privatekey": client_keys["private_key"],
                    "server_publickey": server_wireguard_public_key,
                    "server_ip": remote_ip,
                },
            )
        )

    subprocess.run(
        ["sudo", "wg-quick", "up", conf_path], capture_output=True, check=True
    )


def cmd_start(username, provider, operating_system):
    try:
        subprocess.run(["wg"])
    except FileNotFoundError:
        print("Wireguard client not found")
        sys.exit(1)
    try:
        ip = provider.find_instance_ip()
        logging.info(f"Instance already running at {ip}")

        return
    except AssertionError:
        # Continue
        pass

    # Ensure the SSH agent is running and has a key installed
    result = subprocess.run(["ssh-add", "-l"], capture_output=True, check=False)
    if result.returncode == 1:
        subprocess.run(["ssh-add"], capture_output=True, check=True)

    # Ensure we don't already have an old wireguard instance. And also get sudo permission early for later on.
    subprocess.run(
        ["sudo", "ip", "link", "delete", "wg0"], capture_output=True, check=False
    )

    logging.info("Starting instance")
    provider.create_instance()
    logging.info("Waiting for instance to finalise")
    provider.wait_for_instance()
    ip = provider.find_instance_ip()

    # Delete the existing SSH authorized keys for the IPs we're using
    subprocess.run(
        [
            "sed",
            "-i",
            "-e",
            f"/^{ip}/d",
            "-e",
            "/^10.0.0.1/d",
            os.path.join(os.environ["HOME"], ".ssh/known_hosts"),
        ],
        capture_output=True,
        check=True,
    )

    logging.info(f"Waiting for SSH on {ip} to become available")
    # This also puts the server IP into allowed hosts
    provider.wait_for_ssh(ip)

    logging.info("Setting up basics and server Wireguard")
    client_keys = generate_wireguard_keys()
    provider.specific_setup(ip)
    # Wait again in case we rebooted in specific_setup
    provider.wait_for_ssh(ip, no_host_check=False)
    server_public_key = run_remote_wireguard_setup(
        username, ip, client_keys["public_key"], operating_system
    )
    logging.info("Hooking up client Wireguard")
    set_up_wireguard(ip, client_keys, server_public_key)

    logging.info("Installing 10.0.0.1 SSH key")
    run_ssh_result(username, "10.0.0.1", "true", no_host_check=True)

    logging.info("Done")


def cmd_status(provider):
    status = provider.find_instance_status()
    try:
        ip = provider.find_instance_ip()
        print(f"Instance status {status}, IP {ip}")
    except AssertionError:
        print(f"Instance status {status}")


def cmd_stop(provider):
    logging.info("Terminating instance...")
    provider.terminate_instance()


if __name__ == "__main__":
    config_path = os.path.join(os.environ["HOME"], ".config", "cloudstation.conf")
    config = configparser.ConfigParser()
    config.read(config_path)

    username = "normal"
    provider_label = config["general"]["provider"]
    operating_system = config["general"]["operating_system"]
    provider_config = config[f"provider.{provider_label}"]
    if provider_label == "aws":
        import aws

        provider = aws.Provider(provider_config, operating_system)
    elif provider_label == "vultr":
        import vultr

        provider = vultr.Provider(provider_config, operating_system)
    else:
        raise AssertionError(f"Unknown provider {provider_label}")

    if len(sys.argv) == 1 or sys.argv[1] == "status":
        cmd_status(provider)
    elif sys.argv[1] == "start":
        cmd_start(username, provider, operating_system)
    elif sys.argv[1] == "stop":
        cmd_stop(provider)
    else:
        print("Usage: python cloudstation.py <status|start|stop>")
        sys.exit(1)
