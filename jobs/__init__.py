import os
import importlib.util
from nautobot.apps.jobs import Job, register_jobs

jobs_dir = os.path.dirname(os.path.abspath(__file__))

for root, _, files in os.walk(jobs_dir):
    for file in files:
        if file.endswith(".py") and file != "__init__.py":
            file_path = os.path.join(root, file)
            spec = importlib.util.spec_from_file_location(file[:-3], file_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if isinstance(attr, type) and issubclass(attr, Job) and attr is not Job:
                    attr.__module__ = "nautobot_labs.jobs"
                    register_jobs(attr)
