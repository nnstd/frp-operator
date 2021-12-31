from typing import Dict, Optional, Union
from pydantic.fields import Field
from pydantic.main import BaseModel
from pydantic.types import constr


DNSKey = constr(
    regex=r"^((([A-Za-z0-9][-A-Za-z0-9_.]*)?[A-Za-z0-9])/)?(([A-Za-z0-9][-A-Za-z0-9_.]*)?[A-Za-z0-9])$"
)
LabelValue = constr(regex=r"^(([A-Za-z0-9][-A-Za-z0-9_.]*)?[A-Za-z0-9])?$")
Labels = Dict[DNSKey, LabelValue]
Annotations = Dict[DNSKey, str]


class TemplateMetadata(BaseModel):
    labels: Labels = {}
    annotations: Annotations = {}


class Selector(BaseModel):
    matchLabels: Labels = {}


class TemplateSpec(BaseModel):
    pass


class BaseTemplate(BaseModel):
    metadata: TemplateMetadata = TemplateMetadata()
    spec: TemplateSpec


class NodeNativeResource(BaseModel):
    cpu: Optional[Union[str, int]]
    ephemeral_storage: Optional[Union[str, int]] = Field(alias="ephemeral-storage")
    hugepages_1Gi: Optional[Union[str, int]] = Field(alias="hugepages-1Gi")
    hugepages_2Mi: Optional[Union[str, int]] = Field(alias="hugepages-2Mi")
    memory: Optional[Union[str, int]]


NodeCustomResource = Dict[DNSKey, Union[str, int]]
NodeResource = Union[NodeNativeResource, NodeCustomResource]


class ContainerResources(BaseModel):
    limits: Optional[NodeResource] = None
    requests: Optional[NodeResource] = None
