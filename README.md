Personal scripts to set up and tear down a Fedora workstation on cloud providers (currently Vultr and AWS). Fairly idiosyncratic to the way I have things set up and like them to work, and a little rough around the edges.

# Usage

First set up a ~/.cloudstation.conf file based on cloudstation.example.conf. Next you can use
these commands:

* `python cloudstation.py` - Print whether an instance is already running.
* `python cloudstation.py start` - Start a new instance if one isn't already running. Requires ssh-agent and sudo to work. Will prompt for both of those passwords at the start so you can just type them in and leave.
* `python cloudstation.py stop` - Stop an existing instance.

Once the `start` command has finished you should have the basic Fedora workstation set up and available at fedora@10.0.0.1 (10.0.0.1 being a Wireguard tunnel to it). It will also have an rsync daemon running that lets you sync to the /home/fedora/code/ directory and subdirectories like this:

    rsync -rvnc mydir rsync://10.0.0.1:12000/files/code-subdir

You might want to drop this into your .ssh/config so you can just do `ssh cloudstation`:

    Host cloudstation
        HostName 10.0.0.1
        User fedora

## More provisioning

The python code sets up the basic Wireguard tunnel and rsync. There are some additional scripts included in the repo for provisioning more than that. They can just be used like:

    ssh cloudstation < scripts/docker-workstation.sh

So to do all that in one line and then walk away for 10 minutes:

    python cloudstation.py start && ssh cloudstation < scripts/docker-workstation.sh
