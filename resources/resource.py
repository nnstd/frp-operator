from __future__ import annotations
import copy
from inspect import getmro
from typing import Annotated, Any, ClassVar, Dict, List, Optional, Type
from pydantic import BaseModel, Field
from pydantic.class_validators import validator
from pydantic.fields import PrivateAttr
from pydantic.types import constr
import pykube
from pykube.exceptions import ObjectDoesNotExist
from pykube.http import HTTPClient
from pykube.objects import (
    APIObject,
    NamespacedAPIObject,
    ObjectManager,
    object_factory as pykube_object_factory,
)
from pykube.query import Query, Table
from context import kubeApi, ownerReferences
from contextlib import contextmanager

from resources.common import Annotations, Labels, TemplateMetadata
from copy import deepcopy

DEFAULT = object()


class ModelQuery(object):
    namespace: Optional[str] = None
    type: Type[Resource]

    def __init__(self, namespace: Optional[str], type: Type[Resource]):
        self.namespace = namespace
        self.type = type
        self.query = Query(kubeApi.get(), type._get_pykube_type())

    def get_by_name(self, name: str):
        """
        Get object by name, raises ObjectDoesNotExist if not found
        """
        data = self.query.get_by_name(name)
        return self.type.from_pykube(data)

    def get(self, *args, **kwargs):
        """
        Get a single object by name, namespace, label, ..
        """
        return self.type.from_pykube(self.query.get(*args, **kwargs))

    def get_or_none(self, *args, **kwargs):
        """
        Get object by name, return None if not found
        """
        try:
            return self.get(*args, **kwargs)
        except ObjectDoesNotExist:
            return None

    def watch(self, since=None, *, params=None):
        raise NotImplementedError()
        query = self._clone(WatchQuery)
        query.params = params
        if since is now:
            query.resource_version = self.response["metadata"]["resourceVersion"]
        elif since is not None:
            query.resource_version = since
        return query

    def execute(self, **kwargs):
        return self.query.execute(**kwargs)

    def as_table(self) -> Table:
        """
        Execute query and return result as Table (similar to what kubectl does)
        See https://kubernetes.io/docs/reference/using-api/api-concepts/#receiving-resources-as-tables
        """
        response = self.execute(
            headers={"Accept": "application/json;as=Table;v=v1beta1;g=meta.k8s.io"}
        )
        return Table(self.type._get_pykube_type(), response.json())

    def iterator(self):
        """
        Execute the API request and return an iterator over the objects. This
        method does not use the query cache.
        """
        for obj in self.execute().json().get("items") or []:
            yield self.type.from_pykube(obj)

    @property
    def query_cache(self):
        if not hasattr(self, "_query_cache"):
            cache = {"objects": []}
            cache["response"] = self.execute().json()
            for obj in cache["response"].get("items") or []:
                cache["objects"].append(
                    self.type._get_pykube_type()(kubeApi.get(), obj)
                )
            self._query_cache = cache
        return self._query_cache

    def __len__(self):
        return len(self.query_cache["objects"])

    def __iter__(self):
        return iter(self.query_cache["objects"])

    @property
    def response(self):
        return self.query_cache["response"]


class ModelObjectManager(object):
    cls: Type[Resource]

    def __call__(self, namespace: Optional[str] = None):
        api = kubeApi.get()
        if namespace is None and NamespacedAPIObject in getmro(self.cls):
            namespace = api.config.namespace
        return ModelQuery(namespace=namespace, type=self.cls)

    def setCls(self, cls: Type[Resource]):
        self.cls = cls


class ObjectFactoryCache(object):
    data: Dict[Any, Type[APIObject]]

    def __init__(self):
        self.data = {}

    def __call__(self, apiVersion, kind):
        args = (kubeApi.get(), apiVersion, kind)
        if self.data.get(args, None) is None:
            obj = self.data[args] = pykube_object_factory(*args)
        else:
            obj = self.data[args]
        return obj


object_factory = ObjectFactoryCache()

# https://github.com/asteven/kopf/blob/53d82e5014a2c14e761d4efcce2f05bb3ed90590/kopf/resources.py#L10
def dereference_schema(schema, definitions, parent=None, key=None):
    """Find and dereference objects in the given schema.
    '#/definitions/myElement' -> schema[definitions][myElement]
    """
    if hasattr(schema, "items"):
        for k, v in schema.items():
            if k == "$ref":
                # print('%s -> %s' % (key, v))
                ref_name = v.rpartition("/")[-1]
                definition = definitions[ref_name]
                if isinstance(parent, dict):
                    parent[key] = definition
                elif isinstance(parent, list):
                    parent[parent.index(key)] = definition
                v = definition
            if isinstance(v, dict):
                dereference_schema(v, definitions, parent=schema, key=k)
            elif isinstance(v, list):
                for i, d in enumerate(v):
                    dereference_schema(d, definitions, parent=v, key=d)
    return schema


def fix_defaults(obj: dict):
    for k, v in obj.copy().items():
        if isinstance(v, dict):
            fix_defaults(v)
        if isinstance(v, list):
            for i in v:
                if isinstance(i, dict):
                    fix_defaults(i)
        if v is None:
            del obj[k]
    return obj


def ensure_structural_schema(schema: dict):
    if schema.get("type", None) == "string":
        if (
            schema.get("enum", None) is not None
            and schema.get("default", None) is not None
        ):
            schema["enum"].append(schema["default"])
    if schema.get("type") == "object" and schema.get("default", None) is not None:
        fix_defaults(schema)
    if schema.get("type", None) != "object" and schema.get("type", None) is not None:
        return schema

    if schema.get("patternProperties", None) is not None:
        patternProperties = schema.pop("patternProperties")
        schema["additionalProperties"] = next(iter(patternProperties.values()))

    for property in schema.get("properties", {}).values():
        ensure_structural_schema(property)

    if schema.get("allOf", None) is None:
        return schema

    if len(schema["allOf"]) > 1:
        raise ValueError("Cannot clear multiple allOF")

    schema.update(schema.pop("allOf")[0])

    return ensure_structural_schema(schema)


class OwnerReference(BaseModel):
    apiVersion: str
    kind: str
    name: str
    uid: str
    controller: bool = True
    blockOwnerDeletion: bool = True
    _reset = PrivateAttr()

    def __enter__(self):
        self._reset = ownerReferences.set([self])
        return self

    def __exit__(self, type, value, traceback):
        ownerReferences.reset(self._reset)


class ObjectMeta(TemplateMetadata):
    """Resource ObjectMeta"""

    # https://kubernetes.github.io/cluster-registry/reference/build/index.html#objectmeta-v1
    name: str
    namespace: Optional[str] = None
    uuid: Optional[str] = None
    ownerReferences: List[OwnerReference] = []
    uid: Optional[str] = None
    # TODO: add more of these ...
    # creationTimestamp
    # deletionGracePeriodSeconds
    finalizers: List[str] = Field(default_factory=list)

    @validator("ownerReferences", always=True)
    def validateOwnerReferences(cls, v):
        if v:
            return v
        return ownerReferences.get()


class Subresource(BaseModel):
    ...


class Status(Subresource):
    ...


class Resource(BaseModel):
    __spec__: ClassVar[dict]
    __group__: ClassVar[str]
    __version__: ClassVar[str]
    __kwargs__: ClassVar[Dict[str, Any]]
    __subresources__: ClassVar[List[str]]
    _pykube_obj = PrivateAttr(None)
    _api = PrivateAttr()

    objects: ClassVar[ModelObjectManager] = ModelObjectManager()

    apiVersion: ClassVar[str]
    kind: ClassVar[str]
    metadata: ObjectMeta

    @classmethod
    def _get_pykube_type(cls):
        return object_factory(cls.apiVersion, cls.kind)

    def _get_pykube_obj(self):
        if self._pykube_obj is None:
            self._pykube_obj = self._get_pykube_type()(
                api=kubeApi.get(), obj=self.dict()
            )
        return self._pykube_obj

    def __init_subclass__(
        cls, /, group, version, scope="Namespaced", kind=DEFAULT, **kwargs
    ):
        kind = cls.__name__ if kind is DEFAULT else (cls.kind if kind is None else kind)
        assert isinstance(kind, str)
        cls.__group__ = group
        cls.__version__ = version
        cls.__subresources__ = []
        plural = kwargs.get("plural", f"{kind.lower()}s")
        cls.__spec__ = {
            "group": group,
            "names": {
                "kind": kind,
                "listKind": f"{kind}List",
                "singular": kwargs.get("singular", kind.lower()),
                "plural": plural,
            },
            "scope": scope,
        }
        cls.objects = ModelObjectManager()
        cls.objects.setCls(cls)
        cls.apiVersion = f"{cls.__group__}/{cls.__version__}".removeprefix("/")
        cls.kind = kind
        for key, field in cls.__fields__.items():
            try:
                if issubclass(field.type_, Subresource):
                    cls.__subresources__.append(key)
            except TypeError:
                continue
            if key == "apiVersion":
                field.default = f"{cls.__group__}/{cls.__version__}".removeprefix("/")
                field.required = False
            elif key == "kind":
                field.default = cls.__name__
                field.required = False
        super().__init_subclass__(**kwargs)

    @classmethod
    def as_crd(cls):
        """Create and return a CustomResourceDefinition for this resource."""
        spec = cls.__spec__.copy()
        group = spec["group"]
        plural_name = spec["names"]["plural"]
        body = {
            "apiVersion": "apiextensions.k8s.io/v1",
            "kind": "CustomResourceDefinition",
            "metadata": {"name": f"{plural_name}.{group}"},
            "spec": spec,
        }

        schema = deepcopy(cls.schema())
        if "definitions" in schema:
            definitions = schema.pop("definitions")
            dereference_schema(schema, definitions)
        ensure_structural_schema(schema)

        # Don't want ObjectMeta in crd.
        del schema["properties"]["metadata"]

        # TODO: support different versions?
        version = {
            "name": cls.__version__,
            "schema": {"openAPIV3Schema": schema},
            "served": True,
            "storage": True,
        }
        for subresource in cls.__subresources__:
            version.setdefault("subresources", {})
            version["subresources"][subresource] = {}
        body["spec"]["versions"] = [version]
        return body

    @classmethod
    def from_pykube(cls, obj: APIObject):
        self = cls.parse_obj(obj.obj)
        self._pykube_obj = obj
        return self

    @classmethod
    def get(cls, name, namespace=None):
        obj: APIObject = (
            object_factory(cls.apiVersion, cls.kind)
            .objects(kubeApi.get(), namespace=namespace)
            .get_by_name(name)
        )

        return cls.from_pykube(obj)

    def upsert(self):
        if self.exists():
            self.update()
        else:
            self.create()

    def exists(self, ensure=False):
        # todo: merge logic
        return self._get_pykube_obj().exists(ensure)

    def create(self):
        self._sync()
        self._get_pykube_obj().create()

    def reload(self):
        self._get_pykube_obj().reload()
        self._sync(True)

    def watch(self):
        raise NotImplementedError()
        return (
            self.__class__.objects(self.api, namespace=self.namespace)
            .filter(field_selector={"metadata.name": self.name})
            .watch()
        )

    def patch(self, strategic_merge_patch, *, subresource=None):
        """
        Patch the Kubernetes resource by calling the API with a "strategic merge" patch.
        """
        self._sync()
        self._get_pykube_obj().patch(
            strategic_merge_patch=strategic_merge_patch,
            subresource=subresource,
        )
        self._sync(True)

    def update(self, is_strategic=True, *, subresource=None):
        """
        Update the Kubernetes resource by calling the API (patch)
        """
        self._sync()
        self._get_pykube_obj().update(
            is_strategic=is_strategic,
            subresource=subresource,
        )
        self._sync(True)

    def delete(self, propagation_policy: Optional[str] = None):
        """
        Delete the Kubernetes resource by calling the API.

        The parameter propagation_policy defines whether to cascade the delete. It can be "Foreground", "Background" or "Orphan".
        See https://kubernetes.io/docs/concepts/workloads/controllers/garbage-collection/#setting-the-cascading-deletion-policy
        """
        self._sync(True)
        self._pykube_obj.delete(propagation_policy)  # type: ignore

    def _sync(self, fromPyKube=False):
        if fromPyKube:
            self.__dict__.update(type(self)(**self._get_pykube_obj().obj))
        data = self.dict(by_alias=True)
        data["apiVersion"] = self.apiVersion
        data["kind"] = self.kind
        self._get_pykube_obj().set_obj(data)

    def owner(self, controller=True, blockOwnerDeletion=True):

        return OwnerReference(
            apiVersion=self.apiVersion,
            kind=self.kind,
            name=self.metadata.name,
            uid=self.metadata.uid,  # type: ignore
            controller=controller,
            blockOwnerDeletion=blockOwnerDeletion,
        )
