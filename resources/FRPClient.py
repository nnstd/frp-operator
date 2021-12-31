from typing import Optional
from pydantic.main import BaseModel
from resources.Service import EmbedService
from resources.common import Labels
from resources.resource import Resource
from resources.secret import BasicAuthSecret, TokenSecret


class FRPClientTargetToken(BaseModel):
    secret: str


class FRPClientDashboard(BaseModel):
    credentials: str
    port: int = 7400
    service: EmbedService = EmbedService()


class FRPClientTarget(BaseModel):
    token: FRPClientTargetToken
    host: str
    port: int = 7000


class FRPClientSpec(BaseModel):
    image: str = "snowdreamtech/frpc:latest"
    sidecarImage: str = "registry.nonamestudio.me/gou177/frp-operator:latest"
    selector: Labels = {}
    namespaceSelector: Optional[Labels] = None
    target: FRPClientTarget
    dashboard: Optional[FRPClientDashboard] = None


class FRPClient(
    Resource,
    group="frp.gou177.cyou",
    version="v1",
    scope="Namespaced",
):
    spec: FRPClientSpec

    def config(self):
        token_secret = TokenSecret.get(
            self.spec.target.token.secret, self.metadata.namespace
        ).decode()

        config = "[common]\n"

        config += f"token = {token_secret.data.token}\n"
        config += f"server_addr = {self.spec.target.host}\n"
        config += f"server_port = {self.spec.target.port}\n"

        if self.spec.dashboard:
            dashboard_secret = BasicAuthSecret.get(
                self.spec.dashboard.credentials, self.metadata.namespace
            ).decode()
            config += f"admin_addr = 0.0.0.0\n"
            config += f"admin_port = {self.spec.dashboard.port}\n"
            config += f"admin_user = {dashboard_secret.data.username}\n"
            config += f"admin_pwd = {dashboard_secret.data.password}\n"
        else:
            config += f"admin_addr = 127.0.0.1\n"
            config += f"admin_port = 7400\n"
            config += f"admin_user = sidecar\n"
            config += f"admin_pwd = pwd\n"

        config += f"user = k8s-{self.metadata.namespace}-{self.metadata.name}\n"
        config += f"meta_k8s_ns = {self.metadata.namespace}\n"
        config += f"meta_k8s_name = {self.metadata.name}\n"

        return config
