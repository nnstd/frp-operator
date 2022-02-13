from enum import Enum
from typing import Dict, Literal, Optional, Union, List
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


class FRPClientEndpointSpecBase(BaseModel):
    type: FRPClientEndpointType
    local: FRPClientEndpointLocal
    group: Optional[FRPClientEndpointGroup] = None

    encryption: bool = False
    compression: bool = False
    bandwidthLimit: Optional[str] = None

    additionalConfig: str = ""

    def config(self, name: str):
        config = f"[{name}]\n"
        config += f"type = {self.type}\n"
        config += f"local_ip = {self.local.host}\n"
        config += f"local_port = {self.local.port}\n"
        config += f"use_encryption = {self.encryption}\n"
        config += f"use_compression = {self.compression}\n"

        if self.group:
            config += f"group = {self.group.name}\n"
            config += f"group_key = {self.group.key}\n"

        if self.bandwidthLimit:
            config += f"bandwidth_limit = {self.bandwidthLimit}\n"

        config += f"{self.additionalConfig}\n"
        return config


class FRPClientEndpointSpecL4(FRPClientEndpointSpecBase):
    type: Union[Literal[FRPClientEndpointType.udp], Literal[FRPClientEndpointType.tcp]]

    remote: FRPClientEndpointRemote

    def config(self, name: str):
        config = super().config(name)
        config += f"remote_port = {self.remote.port}\n"

        return config


class FRPClientHttpHealthCheck(BaseModel):
    url: str
    interval: int
    timeout: int = 3
    maxFailed: int = 3


class FRPClientHttp(BaseModel):
    headers: Dict[str, str] = {}
    subdomain: Optional[str] = None
    customDomains: Optional[List[str]] = None
    locations: Optional[List[str]] = None
    hostHeaderRewrite: Optional[str] = None


class FRPClientEndpointSpecHTTP(FRPClientEndpointSpecBase):
    type: Union[
        Literal[FRPClientEndpointType.http], Literal[FRPClientEndpointType.https]
    ]
    http: FRPClientHttp

    def config(self, name: str):
        config = super().config(name)
        if self.http.subdomain:
            config += f"subdomain = {self.http.subdomain}\n"
        if self.http.customDomains:
            config += f"customDomains = {','.join(self.http.customDomains)}\n"
        if self.http.locations:
            config += f"customDomains = {','.join(self.http.locations)}\n"
        if self.http.hostHeaderRewrite:
            config += f"host_header_rewrite = {self.http.hostHeaderRewrite}\n"

        for header, value in self.http.headers.items():
            config += f"header_{header} = {value}"

        return config


class FRPClientEndpointSpec(FRPClientEndpointSpecL4, FRPClientEndpointSpecHTTP):
    type: FRPClientEndpointType
    http: Optional[FRPClientHttp] = None
    remote: Optional[FRPClientEndpointRemote] = None


class FRPClientEndpointModel(BaseModel):
    metadata: ObjectMeta
    spec: Union[FRPClientEndpointSpecL4, FRPClientEndpointSpecHTTP]

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
