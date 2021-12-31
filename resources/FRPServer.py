from typing import List, Literal, Optional, Union

from pydantic import BaseModel
from resources.Deployment import PodContainerPort
from resources.Service import EmbedService
from resources.common import Annotations, Labels

from resources.resource import Resource

from .secret import BasicAuthSecret, BasicAuthSecretData, TokenSecret, TokenSecretData


class FRPServerVHost(BaseModel):
    http: int = 80
    https: Optional[int] = None
    service: EmbedService = EmbedService()


class FRPServerPorts(BaseModel):
    tcp: int = 7000
    udp: int = 7001
    kcp: Optional[int] = 7000


class FRPServerDashboard(BaseModel):
    credentials: str
    port: int = 7500
    service: EmbedService = EmbedService()


class FRPServerToken(BaseModel):
    secret: Optional[str] = None


class FRPServerPlugin(BaseModel):
    name: str
    port: int = 9000
    addr: str = "0.0.0.0"
    path: str = "/handler"
    ops: str

    def config(self):
        return (
            f"[plugin.{self.name}]\n"
            f"addr = {self.addr}:{self.port}\n"
            f"path = {self.path}\n"
            f"ops = {self.ops}\n"
        )


class FRPServerSpec(BaseModel):
    prometheus: bool = True
    allowPorts: Optional[str] = None  # 2000-3000,3001,3003,4000-50000
    plugins: List[FRPServerPlugin] = []
    image: str = "snowdreamtech/frps:latest"
    ports: FRPServerPorts = FRPServerPorts()
    vhost: Optional[FRPServerVHost] = None
    dashboard: Optional[FRPServerDashboard] = None
    token: Optional[FRPServerToken] = None  # if none then auto generate
    service: EmbedService = EmbedService()

    def config(self, namespace: str):
        if not self.token:
            raise ValueError("Token not specified")

        token_secret = TokenSecret.get(self.token.secret, namespace).decode()

        config = "[common]\n"

        config += f"token = {token_secret.data.token}\n"

        config += (
            f"bind_addr = 0.0.0.0\n"
            f"bind_port = {self.ports.tcp}\n"
            f"bind_udp_port = {self.ports.udp}\n"
        )

        if self.ports.kcp:
            config += f"kcp_bind_port = {self.ports.kcp}\n"

        if self.vhost:
            config += f"vhost_http_port = {self.vhost.http}\n"
            if self.vhost.https:
                config += f"vhost_https_port = {self.vhost.https}\n"

        if self.dashboard:
            config += f"dashboard_port = {self.dashboard.port}\n"
            dashboard_creds = BasicAuthSecret.get(
                self.dashboard.credentials, namespace
            ).decode()
            config += f"dashboard_user = {dashboard_creds.data.username}\n"
            config += f"dashboard_pwd = {dashboard_creds.data.password}\n"

        config += f"enable_prometheus = {'true' if self.prometheus else 'false'}\n"

        if self.allowPorts:
            config += f"allow_ports = {self.allowPorts}\n"

        for plugin in self.plugins:
            config += plugin.config()

        return config


class FRPServer(
    Resource,
    group="frp.gou177.cyou",
    version="v1",
    scope="Namespaced",
):
    spec: FRPServerSpec

    def config(self):
        return self.spec.config(self.metadata.namespace)  # type: ignore
