import re
from pydantic import BaseModel
from pydantic.fields import PrivateAttr
import pykube
from base64 import b64decode, b64encode
from context import kubeApi
from resources.resource import Resource
from pydantic import validator


class SecretData(BaseModel):
    _decoded: bool = PrivateAttr(True)

    def decode(self):
        if self._decoded:
            return self
        self = self.copy()
        for k, v in self.dict().items():
            self.__dict__[k] = b64decode(v.encode()).decode()
        return self

    def encode(self):
        if not self._decoded:
            return self
        self = self.copy()
        for k, v in self.dict().items():
            self.__dict__[k] = b64encode(v.encode()).decode()
        return self


class BasicAuthSecretData(SecretData):
    username: str
    password: str


class TokenSecretData(SecretData):
    token: str


class Secret(Resource, group="", version="v1"):
    data: SecretData

    @property
    def _decoded(self):
        return self.data._decoded

    def _sync(self, fromPyKube=False):
        if fromPyKube:
            decoded = self._decoded
            self.__dict__.update(type(self)(**self._get_pykube_obj().obj))
            self.data._decoded = False
            if decoded:
                self.data = self.data.decode()
        data = self.encode().dict(by_alias=True)
        data["apiVersion"] = self.apiVersion
        data["kind"] = self.kind
        self._get_pykube_obj().set_obj(data)

    def encode(self):
        self = self.copy()
        self.data = self.data.encode()
        return self

    def decode(self):
        self = self.copy()
        self.data = self.data.decode()
        return self

    @classmethod
    def from_pykube(cls, obj):
        self = super().from_pykube(obj)
        self.data._decoded = False
        return self


class TokenSecret(Secret, group="", version="v1", kind=None):
    data: TokenSecretData


class BasicAuthSecret(Secret, group="", version="v1", kind=None):
    data: BasicAuthSecretData
