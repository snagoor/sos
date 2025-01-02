# Copyright (c) 2025 Nagoor Shaik <nshaik@redhat.com>

# This file is part of the sos project: https://github.com/sosreport/sos
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# version 2 of the GNU General Public License.
#
# See the LICENSE file in the source distribution for further information.

import os
import subprocess
from sos.report.plugins import Plugin, RedHatPlugin, PluginOpt


class AAPContainerizedPlugin(Plugin, RedHatPlugin):
    """Collects details about AAP Containerized setup
    under a user's home directory"""

    short_desc = "AAP Containerized Setup Plugin"
    plugin_name = "aap_containerized"
    profiles = ("sysmgmt", "ansible",)
    packages = ("podman",)

    option_list = [
        PluginOpt(
            "username",
            default="",
            val_type=[int, str],
            desc="Provide username that was used to setup "
            "AAP containerized installation"
        )
    ]

    def setup(self):
        username = self.get_option("username")
        if not username:
            self._log_debug("Username is mandatory to collect "
                            "AAP containerized setup logs")
            return

        # Grab aap installation directory under user's home
        user_home_directory = os.path.expanduser(f"~{username}")
        aap_directory_name = self.path_join(user_home_directory, "aap")

        # Don't collect cert and key files from the installation directory
        if self.path_exists(aap_directory_name):
            forbidden_paths = [
                self.path_join(aap_directory_name, path)
                for path in [
                    "containers",
                    "tls",
                    "controller/etc/*.cert",
                    "controller/etc/*.key",
                    "eda/etc/*.cert",
                    "eda/etc/*.key",
                    "gateway/etc/*.cert",
                    "gateway/etc/*.key",
                    "hub/etc/*.cert",
                    "hub/etc/*.key",
                    "hub/etc/keys/*.pem",
                    "postgresql/*.crt",
                    "postgresql/*.key",
                    "receptor/etc/*.crt",
                    "receptor/etc/*.key",
                    "receptor/etc/*.pem",
                    "redis/*.crt",
                    "redis/*.key",
                ]
            ]
            self.add_forbidden_path(forbidden_paths)
            self.add_copy_spec(aap_directory_name)
        else:
            self._log_debug(f"Directory {aap_directory_name} does not exist")

        # Gather output of following podman commands as user
        podman_commands = [
            (f"su - {username} -c 'podman info --debug'", "podman_info"),
            (f"su - {username} -c 'podman ps -a --format json'",
                "podman_ps_all_json"),
        ]

        for command, filename in podman_commands:
            self.add_cmd_output(command, suggest_filename=filename)

        # Collect AAP container names
        aap_containers = self._get_aap_container_names(username)

        # Copy podman container log files under plugin sub directory
        # called aap_containers_log
        for container in aap_containers:
            log_file = f"{container}.log"
            self.add_cmd_output(
                    f"su - {username} -c 'podman logs {container}'",
                    suggest_filename=f"{log_file}",
                    subdir="aap_containers_log"
            )

    def _get_aap_container_names(self, username):
        try:
            containers_output = subprocess.check_output(
                ["su", "-", username, "-c",
                 "podman ps -a --format {{.Names}}"],
                text=True
            )
            return containers_output.strip().split("\n")
        except subprocess.CalledProcessError as e:
            self._log_debug(f"Error retrieving Podman containers: {str(e)}")
            return []

    # Check and enable plugin on a AAP Containerized setup
    def check_enabled(self):
        ps = self.exec_cmd("ps aux --noheaders")

        if "awx-manage" in ps["output"] and "aap-gateway" in ps["output"]:
            return True
        return False
