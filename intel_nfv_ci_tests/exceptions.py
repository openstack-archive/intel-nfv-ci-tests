from tempest.lib import exceptions


class HypervisorIPNotFound(exceptions.TempestException):
    message = "Unable to find hypervisor IP for server %(server_id)s"
