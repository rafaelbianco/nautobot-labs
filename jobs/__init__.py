from nautobot.apps.jobs import register_jobs
from .troubleshooting.ping_git import PingViaGit

register_jobs(PingViaGit)
