from typing import Dict, List, Optional

from pydantic.main import BaseModel
from resources.common import BaseTemplate, ContainerResources, Selector, TemplateSpec
from .resource import Resource


class PodContainerVolumeMount(BaseModel):
    name: str
    mountPath: str


class PodContainerProbeHttpGet(BaseModel):
    path: str
    port: int
    host: str = "127.0.0.1"
    scheme: str = "HTTP"


class PodContainerProbe(BaseModel):
    initialDelaySeconds: int = 0
    timeoutSeconds: int = 15
    periodSeconds: int = 10
    successThreshold: int = 1
    failureThreshold: int = 1

    httpGet: Optional[PodContainerProbeHttpGet]


class PodContainerPort(BaseModel):
    name: str
    containerPort: int
    protocol: str = "TCP"


class PodContainerEnv(BaseModel):
    name: str
    value: str


class PodContainer(BaseModel):
    name: str
    image: str
    command: Optional[List[str]] = None
    args: Optional[List[str]] = None
    resources: ContainerResources = ContainerResources()
    volumeMounts: Optional[List[PodContainerVolumeMount]] = None
    livenessProbe: Optional[PodContainerProbe] = None
    startupProbe: Optional[PodContainerProbe] = None
    readinessProbe: Optional[PodContainerProbe] = None
    ports: Optional[List[PodContainerPort]] = None
    env: Optional[List[PodContainerEnv]] = None


class PodVolumeHostPath(BaseModel):
    path: str


class PodVolumeConfigMapItem(BaseModel):
    key: str
    path: str


class PodVolumeConfigMap(BaseModel):
    name: str
    items: Optional[List[PodVolumeConfigMapItem]] = None


class PodVolumeSecret(BaseModel):
    secretName: str


class PodVolume(BaseModel):
    name: str
    hostPath: Optional[PodVolumeHostPath] = None
    configMap: Optional[PodVolumeConfigMap] = None
    emptyDir: Optional[Dict] = None
    secret: Optional[PodVolumeSecret] = None


class DeploymentTemplateSpec(TemplateSpec):
    containers: List[PodContainer]
    initContainers: Optional[List[PodContainer]] = None
    volumes: List[PodVolume] = []


class DeploymentTemplate(BaseTemplate):
    spec: DeploymentTemplateSpec


class DeploymentSpec(BaseModel):
    selector: Selector
    template: DeploymentTemplate


class Deployment(Resource, group="apps", version="v1"):
    spec: DeploymentSpec
