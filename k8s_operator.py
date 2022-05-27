from base64 import b64encode
from typing import List, Optional, cast

from pydantic.fields import Field
from resources.ConfigMap import ConfigMap

from resources.Deployment import (
    Deployment,
    DeploymentSpec,
    DeploymentTemplate,
    DeploymentTemplateSpec,
    PodContainer,
    PodContainerEnv,
    PodContainerPort,
    PodContainerVolumeMount,
    PodVolume,
    PodVolumeSecret,
)
from resources.FRPClient import FRPClient
from resources.FRPClientEndpoint import FRPClientEndpointModel
from resources.FRPServer import FRPServerSpec, FRPServer, FRPServerToken
import kopf
from resources.Namespace import Namespace
from resources.common import Selector, TemplateMetadata

from resources.resource import ObjectMeta
from pydantic import validate_arguments

from resources.secret import Secret, SecretData, TokenSecret, TokenSecretData

import secrets
import hashlib
import apiserver


class FRPSSecretConfig(SecretData):
    config: str = Field(alias="frps.ini")


class FRPCSecretConfig(SecretData):
    config: str = Field(alias="frpc.ini")


@kopf.on.create("frp.gou177.cyou/v1", "FRPServer")
@kopf.on.field("frp.gou177.cyou/v1", "FRPServer", field="spec.token")  # type: ignore
@validate_arguments
def ensure_frp_token(body: FRPServer, new: Optional[FRPServerToken], **kw):
    if new is not None and new.secret:
        return
    token_name = f"frps-{body.metadata.name}-token"

    with body.owner():
        token = secrets.token_urlsafe()
        TokenSecret(
            data=TokenSecretData(token=token),
            metadata=ObjectMeta(
                name=token_name,
                namespace=body.metadata.namespace,
            ),
        ).create()

    body.spec.token = FRPServerToken(secret=token_name)
    body.update()


@kopf.on.update("frp.gou177.cyou/v1", "FRPServer")  # type: ignore
@kopf.on.create("frp.gou177.cyou/v1", "FRPServer")  # type: ignore
@validate_arguments
def create_frp_server_secret(body: FRPServer, **kw):
    with body.owner():
        Secret(
            metadata=ObjectMeta(
                name=f"frps-{body.metadata.name}-config",
                namespace=body.metadata.namespace,
            ),
            data=FRPSSecretConfig.parse_obj({"frps.ini": body.config()}),
        ).upsert()


def get_frpserver_clients_ports(body: FRPServer):
    ports = []
    if body.spec.ports.tcp:
        ports.append(
            PodContainerPort(
                name="tcp",
                containerPort=body.spec.ports.tcp,
            )
        )
    if body.spec.ports.kcp:
        ports.append(
            PodContainerPort(
                name="kcp",
                containerPort=body.spec.ports.tcp,
                protocol="UDP",
            )
        )
    if body.spec.ports.udp:
        ports.append(
            PodContainerPort(
                name="udp",
                containerPort=body.spec.ports.udp,
                protocol="UDP",
            )
        )

    return ports


def get_frpserver_vhost_ports(body: FRPServer):
    ports = []
    if body.spec.vhost:
        ports.append(
            PodContainerPort(
                name="vhost-http",
                containerPort=body.spec.vhost.http,
            )
        )
        if body.spec.vhost.https:
            ports.append(
                PodContainerPort(
                    name="vhost-https",
                    containerPort=body.spec.vhost.https,
                )
            )

    return ports


def get_frpserver_dashboard_ports(body: FRPServer):
    ports = []
    if body.spec.dashboard:
        ports.append(
            PodContainerPort(
                name="dashboard",
                containerPort=body.spec.dashboard.port,
            )
        )
    return ports


def get_frpclient_dashboard_ports(body: FRPClient):
    ports = []
    if body.spec.dashboard:
        ports.append(
            PodContainerPort(
                name="dashboard",
                containerPort=body.spec.dashboard.port,
            )
        )
    return ports


@kopf.on.field("frp.gou177.cyou/v1", "FRPServer", field="spec.service")  # type: ignore
@kopf.on.create("frp.gou177.cyou/v1", "FRPServer")  # type: ignore
@validate_arguments
def create_frp_server_clients_service(body: FRPServer, **kw):
    with body.owner():
        ports: List[PodContainerPort] = get_frpserver_clients_ports(body)
        udp = []
        tcp = []
        for port in ports:
            if port.protocol == "TCP":
                tcp.append(port)
            else:
                udp.append(port)
        if not ports:
            return
        if udp:
            body.spec.service.forPorts(
                udp,
                get_frpserver_deploy_labels(body),
                cast(str, body.metadata.namespace),
                f"frps-{body.metadata.name}-udp",
            ).upsert()
        if tcp:
            body.spec.service.forPorts(
                tcp,
                get_frpserver_deploy_labels(body),
                cast(str, body.metadata.namespace),
                f"frps-{body.metadata.name}-tcp",
            ).upsert()


@kopf.on.field("frp.gou177.cyou/v1", "FRPServer", field="spec.dashboard.service")  # type: ignore
@kopf.on.create("frp.gou177.cyou/v1", "FRPServer")  # type: ignore
@validate_arguments
def create_frp_server_dashboard_service(body: FRPServer, **kw):
    with body.owner():
        ports: List[PodContainerPort] = get_frpserver_dashboard_ports(body)
        if ports and body.spec.dashboard:
            body.spec.dashboard.service.forPorts(
                ports,
                get_frpserver_deploy_labels(body),
                cast(str, body.metadata.namespace),
                f"frps-{body.metadata.name}-dashboard",
            ).upsert()


@kopf.on.field("frp.gou177.cyou/v1", "FRPServer", field="spec.vhost.service")  # type: ignore
@kopf.on.create("frp.gou177.cyou/v1", "FRPServer")  # type: ignore
@validate_arguments
def create_frp_server_vhost_service(body: FRPServer, **kw):
    with body.owner():
        ports: List[PodContainerPort] = get_frpserver_vhost_ports(body)
        if ports and body.spec.vhost:
            body.spec.vhost.service.forPorts(
                ports,
                get_frpserver_deploy_labels(body),
                cast(str, body.metadata.namespace),
                f"frps-{body.metadata.name}-vhost",
            ).upsert()


def get_frpserver_deploy_labels(body: FRPServer):
    return {
        "app": "frp-server",
        "frpserver.frp.gou177.cyou/name": body.metadata.name,
    }


def get_frpclient_deploy_labels(body: FRPClient):
    return {
        "app": "frp-client",
        "frpserver.frp.gou177.cyou/name": body.metadata.name,
    }


@kopf.on.update("frp.gou177.cyou/v1", "FRPServer")  # type: ignore
@kopf.on.create("frp.gou177.cyou/v1", "FRPServer")  # type: ignore
@validate_arguments
def create_frp_server_deploy(body: FRPServer, **kw):
    with body.owner():
        labels = get_frpserver_deploy_labels(body)
        labels.update(
            {
                "frp.gou177.cyou/config-md5": hashlib.md5(
                    body.config().encode()
                ).hexdigest()
            }
        )
        ports = (
            get_frpserver_clients_ports(body)
            + get_frpserver_vhost_ports(body)
            + get_frpserver_dashboard_ports(body)
        )
        Deployment(
            metadata=ObjectMeta(
                name=f"frps-{body.metadata.name}", namespace=body.metadata.namespace
            ),
            spec=DeploymentSpec(
                template=DeploymentTemplate(
                    metadata=TemplateMetadata(labels=labels),
                    spec=DeploymentTemplateSpec(
                        containers=[
                            PodContainer(
                                name="frp-server",
                                image=body.spec.image,
                                ports=ports,
                                volumeMounts=[
                                    PodContainerVolumeMount(
                                        name="config", mountPath="/etc/frp"
                                    ),
                                ],
                            )
                        ],
                        volumes=[
                            PodVolume(
                                secret=PodVolumeSecret(
                                    secretName=f"frps-{body.metadata.name}-config"
                                ),
                                name="config",
                            ),
                        ],
                    ),
                ),
                selector=Selector(matchLabels=get_frpserver_deploy_labels(body)),
            ),
        ).upsert()


@kopf.on.update("frp.gou177.cyou/v1", "FRPClient")  # type: ignore
@kopf.on.create("frp.gou177.cyou/v1", "FRPClient")  # type: ignore
@validate_arguments
def create_frp_client_secret(body: FRPClient, **kw):
    with body.owner():
        Secret(
            metadata=ObjectMeta(
                name=f"frpc-{body.metadata.name}-config",
                namespace=body.metadata.namespace,
            ),
            data=FRPCSecretConfig.parse_obj({"frpc.ini": body.config()}),
        ).upsert()


@kopf.on.update("frp.gou177.cyou/v1", "FRPClient")  # type: ignore
@kopf.on.create("frp.gou177.cyou/v1", "FRPClient")  # type: ignore
@validate_arguments
def create_frp_client_deploy(body: FRPClient, **kw):
    with body.owner():
        labels = get_frpclient_deploy_labels(body)
        labels.update(
            {
                "frp.gou177.cyou/config-md5": hashlib.md5(
                    body.config().encode()
                ).hexdigest()
            }
        )
        ports = get_frpclient_dashboard_ports(body)
        assert body.metadata.namespace

        Deployment(
            metadata=ObjectMeta(
                name=f"frpc-{body.metadata.name}", namespace=body.metadata.namespace
            ),
            spec=DeploymentSpec(
                template=DeploymentTemplate(
                    metadata=TemplateMetadata(labels=labels),
                    spec=DeploymentTemplateSpec(
                        containers=[
                            PodContainer(
                                name="frp-server",
                                image=body.spec.image,
                                ports=ports,
                                volumeMounts=[
                                    PodContainerVolumeMount(
                                        name="config", mountPath="/etc/frp"
                                    ),
                                ],
                            ),
                            PodContainer(
                                name="sidecar",
                                image=body.spec.sidecarImage,
                                ports=ports,
                                command=["python", "sidecar.py"],
                                volumeMounts=[
                                    PodContainerVolumeMount(
                                        name="default-config",
                                        mountPath="/config/default",
                                    ),
                                    PodContainerVolumeMount(
                                        name="config", mountPath="/config/frp"
                                    ),
                                ],
                                env=[
                                    PodContainerEnv(
                                        name="NAME", value=body.metadata.name
                                    ),
                                    PodContainerEnv(
                                        name="NAMESPACE", value=body.metadata.namespace
                                    ),
                                ],
                            ),
                        ],
                        volumes=[
                            PodVolume(
                                secret=PodVolumeSecret(
                                    secretName=f"frpc-{body.metadata.name}-config"
                                ),
                                name="default-config",
                            ),
                            PodVolume(
                                emptyDir={},
                                name="config",
                            ),
                        ],
                    ),
                ),
                selector=Selector(matchLabels=get_frpclient_deploy_labels(body)),
            ),
        ).upsert()


@kopf.on.update("frp.gou177.cyou/v1", "FRPClientEndpoint")  # type: ignore
@kopf.on.create("frp.gou177.cyou/v1", "FRPClientEndpoint")  # type: ignore
@kopf.on.resume("frp.gou177.cyou/v1", "FRPClientEndpoint")  # type: ignore
@validate_arguments
def update_endpoints(body: FRPClientEndpointModel, **kw):
    if body.metadata.namespace:
        apiserver.endpoints.setdefault(body.metadata.namespace, {}).update(
            {body.metadata.name: body}
        )


@kopf.on.delete("frp.gou177.cyou/v1", "FRPClientEndpoint")  # type: ignore
@validate_arguments
def delete_endpoint(body: FRPClientEndpointModel, **kw):
    if body.metadata.namespace:
        apiserver.endpoints.setdefault(body.metadata.namespace, {}).pop(
            body.metadata.name, None
        )


@kopf.on.create("namespace")  # type: ignore
@kopf.on.resume("namespace")  # type: ignore
@validate_arguments
def update_namespaces(body: Namespace, **kw):
    apiserver.namespaces.setdefault(body.metadata.name, body)
        


@kopf.on.delete("namespace", optional=True)  # type: ignore
@validate_arguments
def delete_namespaces(body: Namespace, **kw):
    if body.metadata.namespace:
        apiserver.namespaces.pop(body.metadata.name, None)
