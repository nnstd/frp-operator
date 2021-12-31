from typing import Dict
from .resource import Resource


class ConfigMap(Resource, group="", version="v1"):
    data: Dict[str, str] = {}
