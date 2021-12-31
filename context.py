import pykube
from contextvars import ContextVar

api = pykube.HTTPClient(pykube.KubeConfig.from_env())

kubeApi = ContextVar("kubeApi", default=api)
ownerReferences = ContextVar("ownerReferences", default=[])