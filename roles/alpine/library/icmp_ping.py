#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) 2019, Ansible by Red Hat, inc
# (c) 2019 Kevin Gallagher (@ageis) <kevingallagher@gmail.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# from https://gist.github.com/wenerme/24162efcdaf978f5eb3ae8e220390c62

from __future__ import absolute_import, division, print_function

ANSIBLE_METADATA = {"metadata_version": "1.1", "status": ["preview"], "supported_by": "community"}
__metaclass__ = type
import re
import locale
import os
from ansible.module_utils.basic import *

DOCUMENTATION = r"""
---
module: icmp_ping
version_added: "2.8"
author: "Kevin Gallagher (@ageis)"
short_description: Tests reachability using ping.
requirements: [ ping, netifaces ]
description:
  - Tests reachability using ping to a remote destination.
options:
  dest:
    description:
    - The IP Address or hostname of the remote node to ping.
    type: str
    required: True
  source:
    description:
    - An address or interface name to send packets from.
    type: str
    default: eth0
    required: False
  count:
    description:
    - Number of packets to send.
    type: int
    default: 5
    required: False
  timeout:
    description:
    - Time to wait for a response, in seconds.
    type: int
    default: 3
    required: False
  interval:
    description:
    - Wait interval seconds between sending each packet.
    type: int
    default: 1
  ttl:
    description:
    - Set the IP Time to Live.
    type: int
    default: 64
    required: False
  size:
    description:
    - Specifies the number of data bytes to be sent.
    type: int
    default: 56
    required: False
  state:
    description:
      - Determines if the expected result is success or fail.
    choices: [ absent, present ]
    default: present
    required: False
"""

EXAMPLES = r"""
- name: Test reachability to 1.1.1.1.
  icmp_ping:
    dest: 1.1.1.1
- name: Test unreachability to 8.8.8.8 using interval
  icmp_ping:
    dest: 8.8.8.8
    interval: 3
    state: absent
- name: Test reachability to 10.0.1.1 setting count and source
  icmp_ping:
    dest: 10.0.1.1
    source: eth1
    count: 20
    size: 512
"""

RETURN = """
msg:
  description: Output from the ping command
  returned: always
  type: str
  sample: |-
    PING 127.0.0.1 (127.0.0.1) from 127.0.0.1 : 56(84) bytes of data.
    64 bytes from 127.0.0.1: icmp_seq=1 ttl=64 time=0.023 ms
    64 bytes from 127.0.0.1: icmp_seq=2 ttl=64 time=0.038 ms
    64 bytes from 127.0.0.1: icmp_seq=3 ttl=64 time=0.022 ms
    64 bytes from 127.0.0.1: icmp_seq=4 ttl=64 time=0.047 ms
    64 bytes from 127.0.0.1: icmp_seq=5 ttl=64 time=0.022 ms
    --- 127.0.0.1 ping statistics ---
    5 packets transmitted, 5 received, 0% packet loss, time 97ms
    rtt min/avg/max/mdev = 0.022/0.030/0.047/0.011 ms
packet_loss:
  description: Percentage of packets lost.
  returned: always
  type: str
  sample: "0%"
packets_rx:
  description: Packets successfully received.
  returned: always
  type: int
  sample: 20
packets_tx:
  description: Packets successfully transmitted.
  returned: always
  type: int
  sample: 20
rtt:
  description: The round trip time (RTT) stats.
  returned: when ping succeeds
  type: dict
  sample: {"avg": 2, "max": 8, "min": 1, "mdev": 24}
"""


def which(program):
    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

    fpath, fname = os.path.split(program)
    if fpath:
        if is_exe(program):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file
    return None


def parse_rate(rate_info):
    # busybox 4 packets transmitted, 4 packets received, 0% packet loss
    # macos   4 packets transmitted, 4 packets received, 0.0% packet loss, 4 packets out of wait time
    rate_re = re.compile(
        r"(?P<tx>\d+)[^,]+, (?P<rx>\d+)[^,]+, (?P<pkt_loss>\d+)"
    )
    rate_err_re = re.compile(
        r"(?P<tx>\d+)[^,]+, (?P<rx>\d+)[^,]+, (?:[+-])(?P<err>\d+)[^,]+, (?P<pkt_loss>\d+)"
    )

    if rate_re.match(rate_info):
        rate = rate_re.match(rate_info)
    elif rate_err_re.match(rate_info):
        rate = rate_err_re.match(rate_info)

    return rate.group("pkt_loss"), rate.group("rx"), rate.group("tx")


def parse_rtt(rtt_info):
    # busybox round-trip min/avg/max = 32.178/35.193/40.394 ms
    # maxos   round-trip min/avg/max/stddev = 30.805/32.854/33.717/1.190 ms
    rtt_re = re.compile(
        r"[^=]+=\s*(?P<min>\d+)[^/]*/(?P<avg>\d+)[^/]*/(?P<max>\d+)[^/]*(/(?P<mdev>\d+))?"
    )
    rtt = rtt_re.match(rtt_info)

    return rtt.groupdict()


def validate_results(module, loss, results):
    state = module.params["state"]
    if state == "present" and int(loss) == 100:
        module.fail_json(msg="Ping failed unexpectedly.", **results)
    elif state == "absent" and int(loss) < 100:
        module.fail_json(msg="Ping succeeded unexpectedly.", **results)

# def module_exists(module_name):


def run_module():
    # default_interface = netifaces.gateways()["default"][netifaces.AF_INET][1]
    # ansible_facts ansible_default_ipv4.interface
    default_interface = "eth0"
    try:
        netifaces = __import__("netifaces")
        default_interface = netifaces.gateways()["default"][netifaces.AF_INET][1]
    except ImportError:
        pass

    module_args = dict(
        dest=dict(required=True, type="str"),
        source=dict(type="str", required=False, default=default_interface),
        count=dict(required=False, default=5, type="int"),
        timeout=dict(required=False, default=3, type="int"),
        interval=dict(required=False, default=1, type="int"),
        ttl=dict(type="int", required=False, default=64),
        size=dict(type="int", required=False, default=56),
        state=dict(type="str", choices=["absent", "present"], default="present"),
    )
    result = dict(changed=False, original_message="", message="")
    module = AnsibleModule(argument_spec=module_args, supports_check_mode=True)
    module.run_command_environ_update = dict(LANG="C", LC_ALL="C", LC_MESSAGES="C", LC_CTYPE="C")
    locale.setlocale(locale.LC_ALL, "C")
    ping_params = dict(
        {
            "dest": None,
            "source": default_interface,
            "count": 5,
            "timeout": 3,
            "interval": 1,
            "ttl": 64,
            "size": 56,
            "state": "present",
        }
    )

    dest = module.params["dest"]
    source = module.params["source"]
    count = module.params["count"]
    timeout = module.params["timeout"]
    interval = module.params["interval"]
    ttl = module.params["ttl"]
    size = module.params["size"]
    state = module.params["state"]
    warnings = list()

    if ttl not in range(1, 255):
        module.fail_json(msg="The TTL %s (IP Time to Live) value must be between 1 and 255." % ttl)

    for param in ping_params.keys():
        module_param = module.params.get(param)
        if module_param is not None:
            ping_params[param] = module_param
    if not which("ping"):
        module.fail_json(msg="The 'ping' executable does not exist in the PATH.")

    # cannot set source interface without root privileges
    if os.geteuid() != 0:
        ping_results = module.run_command(
            # NOTE busybox no -B macos no -4
            # "ping -4 -B -c {} -i {} -W {} -s {} -t {} {}".format(
            "ping -c {} -i {} -W {} -s {} -t {} {}".format(
                ping_params["count"],
                ping_params["interval"],
                ping_params["timeout"],
                ping_params["size"],
                ping_params["ttl"],
                ping_params["dest"],
            )
        )
    else:
        ping_results = module.run_command(
            "ping -4 -I {} -c {} -i {} -W {} -s {} -t {} {}".format(
                ping_params["source"],
                ping_params["count"],
                ping_params["interval"],
                ping_params["timeout"],
                ping_params["size"],
                ping_params["ttl"],
                ping_params["dest"],
            )
        )

    ping_results_list = ping_results[1].split("\n")

    results = {}
    if warnings:
        results["warnings"] = warnings

    rtt_info, rate_info = None, None
    for line in ping_results_list:
        if "min/avg/max" in line:
            rtt_info = line
        if "packets transmitted" in line:
            rate_info = line

    if rtt_info:
        rtt = parse_rtt(rtt_info)
        for k, v in rtt.items():
            if rtt[k] is not None:
                rtt[k] = int(v)
        results["rtt"] = rtt

    pkt_loss, rx, tx = parse_rate(rate_info)
    results["packet_loss"] = str(pkt_loss) + "%"
    results["packets_rx"] = int(rx)
    results["packets_tx"] = int(tx)
    validate_results(module, pkt_loss, results)
    failed = ping_results[0] != 0
    msg = ping_results[1] if ping_results[1] else ping_results[2]
    module.exit_json(changed=False, failed=failed, msg=msg, **results)


def main():
    run_module()


if __name__ == "__main__":
    main()
