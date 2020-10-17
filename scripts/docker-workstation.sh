#!/bin/bash

# Need to turn off a systemd thing for Docker to work for the moment
sudo sed -i -e '/^GRUB_CMD/d' -e '1 a GRUB_CMDLINE_LINUX=\"no_timer_check net.ifnames=0 console=tty1 console=ttyS0,115200n8 systemd.unified_cgroup_hierarchy=0\"' /etc/default/grub
sudo grub2-mkconfig
sudo dnf update -y
sudo dnf -y install dnf-plugins-core
sudo dnf config-manager --add-repo https://download.docker.com/linux/fedora/docker-ce.repo
sudo dnf install -y docker-ce docker-ce-cli containerd.io mosh git screen vim-enhanced docker-compose bash-completion make
sudo usermod -aG docker $USER
sudo systemctl enable docker
# Make sure file watcher like node.js aren't curtailed
echo fs.inotify.max_user_watches=524288 | sudo tee -a /etc/sysctl.conf && sudo sysctl -p

# Need to reboot for the kernel commandline to be picked up
sudo reboot
