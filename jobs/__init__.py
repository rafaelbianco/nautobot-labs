from nautobot.apps.jobs import register_jobs
from nautobot_labs.jobs.troubleshooting.ping_git import PingViaGit

PingViaGit.__module__ = "nautobot_labs.jobs"
register_jobs(PingViaGit)
