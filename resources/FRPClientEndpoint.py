from enum import Enum
from typing import Literal, Optional, Union
from pydantic.main import BaseModel

from resources.resource import ObjectMeta, Resource


class FRPClientEndpointType(str, Enum):
    tcp = "tcp"
    udp = "udp"
    http = "http"
    https = "https"
    stcp = "stcp"
    xtcp = "xtcp"


class FRPClientEndpointLocal(BaseModel):
    host: str
    port: int


class FRPClientEndpointRemote(BaseModel):
    port: int


class FRPClientEndpointGroup(BaseModel):
    name: str
    key: str


class FRPClientEndpointSpecL4(BaseModel):
    type: Union[Literal[FRPClientEndpointType.udp], Literal[FRPClientEndpointType.tcp]]

    remote: FRPClientEndpointRemote
    local: FRPClientEndpointLocal
    group: Optional[FRPClientEndpointGroup] = None

    encryption: bool = False
    compression: bool = False
    bandwidthLimit: Optional[str] = None

    def config(self, name: str):
        config = f"[{name}]\n"
        config += f"type = {self.type}\n"
        config += f"local_ip = {self.local.host}\n"
        config += f"local_port = {self.local.port}\n"
        config += f"remote_port = {self.remote.port}\n"
        config += f"use_encryption = {self.encryption}\n"
        config += f"use_compression = {self.compression}\n"

        if self.group:
            config += f"group = {self.group.name}\n"
            config += f"remote_port = {self.group.key}\n"

        if self.bandwidthLimit:
            config += f"bandwidth_limit = {self.bandwidthLimit}"
        return config


class FRPClientEndpointSpec(FRPClientEndpointSpecL4):
    type: FRPClientEndpointType


class FRPClientEndpointModel(BaseModel):
    metadata: ObjectMeta
    spec: FRPClientEndpointSpecL4

    def toResource(self):
        return FRPClientEndpoint.parse_obj(self.dict(by_alias=True))

    def config(self):
        return self.spec.config(f"{self.metadata.namespace}_{self.metadata.name}")


class FRPClientEndpoint(
    Resource,
    group="frp.gou177.cyou",
    version="v1",
):
    spec: FRPClientEndpointSpec

    def toModel(self):
        return FRPClientEndpointModel.parse_obj(self.dict(by_alias=True))
