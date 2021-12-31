import asyncio
import logging
import os
import socket
import sys
import threading
import typing
from os import getenv

import uvicorn
from asgiref.typing import ASGIApplication
from fastapi import FastAPI
from uvicorn.config import Config
from uvicorn.server import Server
from resources.FRPClient import FRPClient
from resources.FRPClientEndpoint import FRPClientEndpoint, FRPClientEndpointModel
from resources.FRPServer import FRPServer
from resources.Namespace import Namespace
from resources.common import Labels

app = FastAPI()
endpoints: typing.Dict[str, typing.Dict[str, FRPClientEndpointModel]] = {}
namespaces: typing.Dict[str, Namespace] = {}


@app.get("/frps/{namespace}/{name}/config")
def get_frps_config(namespace: str, name: str):
    return FRPServer.get(name, namespace).config()


def matchLabelsBySelector(selector: Labels, labels: Labels):
    for key, value in selector.items():
        if labels.get(key, None) != value:
            return False
    return True


@app.get("/frpc/{namespace}/{name}/config/services")
def get_frpc_services_config(namespace: str, name: str):
    client = FRPClient.get(name, namespace)
    selectedNamespaces = [namespaces[namespace]]
    selectedEnpoints: typing.List[FRPClientEndpointModel] = []

    if client.spec.namespaceSelector is not None:
        selectedNamespaces = []
        for ns in namespaces.values():
            if matchLabelsBySelector(client.spec.namespaceSelector, ns.metadata.labels):
                selectedNamespaces.append(ns)

    for ns in selectedNamespaces:
        for endpoint in endpoints.get(ns.metadata.name, {}).values():
            if matchLabelsBySelector(client.spec.selector, endpoint.metadata.labels):
                selectedEnpoints.append(endpoint)

    return {"config": "\n".join(map(FRPClientEndpointModel.config, selectedEnpoints))}


class AsyncServer(Server):
    def run(self, sockets: typing.Optional[typing.List[socket.socket]] = None) -> None:
        self.config.setup_event_loop()
        asyncio.get_event_loop().create_task(self.serve(sockets=sockets))


def run_async(app: typing.Union[ASGIApplication, str], **kwargs: typing.Any) -> None:
    config = Config(app, **kwargs)
    server = AsyncServer(config=config)

    if (config.reload or config.workers > 1) and not isinstance(app, str):
        logger = logging.getLogger("uvicorn.error")
        logger.warning(
            "You must pass the application as an import string to enable 'reload' or "
            "'workers'."
        )
        sys.exit(1)

    server.run()
    if config.uds:
        os.remove(config.uds)


if __name__ == "__main__":
    uvicorn.run(app, port=int(getenv("PORT", 4032)), host="0.0.0.0")  # type: ignore
else:
    run_async(app, port=int(getenv("PORT", 4032)), host="0.0.0.0")  # type: ignore
