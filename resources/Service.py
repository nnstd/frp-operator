from enum import Enum
from typing import List, Literal, Optional, Union

from pydantic.main import BaseModel
from .resource import ObjectMeta, Resource
from .common import Labels, Annotations
from .Deployment import PodContainerPort


class ServiceType(str, Enum):
    ClusterIP = "ClusterIP"
    LoadBalancer = "LoadBalancer"


class ServicePort(BaseModel):
    name: str
    protocol: str = "TCP"
    port: int
    targetPort: Union[int, str]


class ServiceSpec(BaseModel):
    ports: List[ServicePort] = []
    selector: Labels
    type: ServiceType = ServiceType.ClusterIP
    allocateLoadBalancerNodePorts: Optional[bool]


class Service(Resource, group="", version="v1"):
    spec: ServiceSpec


class EmbedService(BaseModel):
    labels: Labels = {}
    annotations: Annotations = {}
    type: ServiceType = ServiceType.ClusterIP
    allocateLoadBalancerNodePorts: Optional[bool] = None

    def forPorts(
        self,
        ports: List[PodContainerPort],
        selector: Labels,
        namespace: str,
        name: str,
    ):
        return Service(
            metadata=ObjectMeta(
                labels=self.labels,
                annotations=self.annotations,
                name=name,
                namespace=namespace,
            ),
            spec=ServiceSpec(
                ports=[
                    ServicePort(
                        name=port.name,
                        protocol=port.protocol,
                        port=port.containerPort,
                        targetPort=port.name,
                    )
                    for port in ports
                ],
                allocateLoadBalancerNodePorts=self.allocateLoadBalancerNodePorts,
                type=self.type,
                selector=selector,
            ),
        )
