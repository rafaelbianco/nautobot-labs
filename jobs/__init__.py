import os
import sys
import pkgutil
import importlib
from nautobot.apps.jobs import Job, register_jobs

# Garante que a raiz do repositório Git está no sys.path para imports de subpastas funcionarem
repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

for _, module_name, _ in pkgutil.walk_packages(__path__, prefix=f"{__name__}."):
    module = importlib.import_module(module_name)
    for attr_name in dir(module):
        attr = getattr(module, attr_name)
        if isinstance(attr, type) and issubclass(attr, Job) and attr is not Job:
            attr.__module__ = __name__
            register_jobs(attr)
