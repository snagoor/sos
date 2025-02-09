# Copyright (c) 2025 Nagoor Shaik <nshaik@redhat.com>

# This file is part of the sos project: https://github.com/sosreport/sos
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# version 2 of the GNU General Public License.
#
# See the LICENSE file in the source distribution for further information.

import os
from sos.report.plugins import Plugin, RedHatPlugin, PluginOpt


class AAPContainerized(Plugin, RedHatPlugin):
    """Collects details about AAP Containerized setup
    under a user's home directory"""

    short_desc = "AAP Containerized Setup"
    plugin_name = "aap_containerized"
    profiles = ("sysmgmt", "ansible",)
    packages = ("podman",)

    option_list = [
        PluginOpt(
            "username",
            default="",
            val_type=str,
            desc="Username that was used to setup "
            "AAP containerized installation"
        ),
        PluginOpt(
            "directory",
            default="",
            val_type=str,
            desc="Absolute path to AAP containers volume directory. "
            "Defaults to 'aap' under provided user's home directory"
        )
    ]

    def setup(self):
        # Check if username is passed as argument
        username = self.get_option("username")
        if not username:
            self._log_error("Username is mandatory to collect "
                            "AAP containerized setup logs")
            return

        # Grab aap installation directory under user's home
        if not self.get_option("directory"):
            user_home_directory = os.path.expanduser(f"~{username}")
            aap_directory_name = self.path_join(user_home_directory, "aap")
        else:
            aap_directory_name = self.get_option("directory")

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
            self._log_error(f"Directory {aap_directory_name} does not exist "
                            "or invalid absolute path provided")

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

        # Copy podman container log files in plugin sub directory
        # under aap_containers_log
        for container in aap_containers:
            log_file = f"{container}.log"
            self.add_cmd_output(
                    f"su - {username} -c 'podman logs {container}'",
                    suggest_filename=f"{log_file}",
                    subdir="aap_containers_log"
            )

    # Function to fetch podman container names
    def _get_aap_container_names(self, username):
        try:
            cmd = f"su - {username} -c 'podman ps -a --format {{{{.Names}}}}'"
            cmd_out = self.exec_cmd(cmd)
            if cmd_out['status'] == 0:
                return cmd_out['output'].strip().split("\n")
            return []
        except Exception:
            self._log_error("Error retrieving Podman containers")
            return []

    # Check and enable plugin on a AAP Containerized host
    def check_enabled(self):
        aap_processes = [
                'dumb-init -- /usr/bin/envoy',
                'dumb-init -- /usr/bin/supervisord',
                'dumb-init -- /usr/bin/launch_awx_web.sh',
                'dumb-init -- /usr/bin/launch_awx_task.sh',
                'pulpcore-content --name pulp-content --bind',
                'dumb-init -- aap-eda-manage',
            ]

        ps_output = self.exec_cmd("ps --noheaders -eo args")

        if ps_output['status'] == 0:
            for process in aap_processes:
                if process in ps_output['output']:
                    return True
        return False
