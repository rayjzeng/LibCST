# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

# pyre-strict
from types import MappingProxyType
from typing import (
    TYPE_CHECKING,
    Any,
    Generic,
    Iterable,
    Mapping,
    MutableMapping,
    Type,
    TypeVar,
    cast,
)

from libcst._batched_visitor import BatchableCSTVisitor
from libcst._visitors import CSTVisitor
from libcst.metadata.dependent import (
    _T as _MetadataT,
    _UNDEFINED_DEFAULT,
    _MetadataDependent,
)


if TYPE_CHECKING:
    from libcst._nodes._base import CSTNode
    from libcst._nodes._module import Module, _ModuleSelfT as _ModuleT
    from libcst.metadata.wrapper import MetadataWrapper


ProviderT = Type["BaseMetadataProvider[Any]"]
_T = TypeVar("_T")


# We can't use an ABCMeta here, because of metaclass conflicts
class BaseMetadataProvider(_MetadataDependent, Generic[_T]):
    """
    Abstract base class for all metadata providers.
    """

    # Cache of metadata computed by this provider
    _computed: MutableMapping["CSTNode", _T]

    def __init__(self) -> None:
        super().__init__()
        self._computed = {}

    def _gen(self, wrapper: "MetadataWrapper") -> Mapping["CSTNode", _T]:
        """
        Returns metadata mapping for this provider on wrapper.

        This is a hook for metadata resolver and should not be called directly.
        """

        self._computed = {}
        # Resolve metadata dependencies for this provider
        with self.resolve(wrapper):
            self._gen_impl(wrapper.module)

        # Copy into a mapping proxy to ensure immutability
        return MappingProxyType(dict(self._computed))

    def _gen_impl(self, module: "Module") -> None:
        """
        Override this method to compute metadata using set_metadata.
        """
        ...

    def set_metadata(self, node: "CSTNode", value: _T) -> None:
        """
        Map a given node to a metadata value.
        """
        self._computed[node] = value

    def get_metadata(
        self,
        key: Type["BaseMetadataProvider[_MetadataT]"],
        node: "CSTNode",
        default: _MetadataT = _UNDEFINED_DEFAULT,
    ) -> _MetadataT:
        """
        Override to query from self._computed in addition to self.metadata.
        """
        if key is type(self):
            if default is not _UNDEFINED_DEFAULT:
                return cast(_MetadataT, self._computed.get(node, default))
            else:
                return cast(_MetadataT, self._computed[node])

        return super().get_metadata(key, node, default)


class VisitorMetadataProvider(CSTVisitor, BaseMetadataProvider[_T]):
    """
    Extend this to compute metadata with a non-batchable visitor.
    """

    def _gen_impl(self, module: "_ModuleT") -> None:
        module.visit(self)


class BatchableMetadataProvider(BatchableCSTVisitor, BaseMetadataProvider[_T]):
    """
    Extend this to compute metadata with a batchable visitor.
    """

    def _gen_impl(self, module: "Module") -> None:
        """
        Batchables providers are resolved through _gen_batchable] so no
        implementation should be provided in _gen_impl.
        """
        pass


def _gen_batchable(
    wrapper: "MetadataWrapper",
    # pyre-fixme[2]: Parameter `providers` must have a type that does not contain `Any`
    providers: Iterable[BatchableMetadataProvider[Any]],
) -> Mapping[ProviderT, Mapping["CSTNode", object]]:
    """
    Returns map of metadata mappings from the given batchable providers on 
    wrapper.
    """
    wrapper.visit_batched(providers)

    # Make immutable metadata mapping
    # pyre-ignore[7]
    return {type(p): MappingProxyType(dict(p._computed)) for p in providers}
