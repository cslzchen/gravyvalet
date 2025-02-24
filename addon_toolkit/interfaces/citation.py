import dataclasses
from enum import (
    StrEnum,
    auto,
)


__all__ = (
    "ItemSampleResult",
    "CitationConfig",
    "ItemType",
    "ItemResult",
    "CitationServiceInterface",
    "CitationAddonImp",
)

from addon_toolkit import (
    AddonCapabilities,
    AddonImp,
    immediate_operation,
)
from addon_toolkit.constrained_network.http import HttpRequestor

from ._base import BaseAddonInterface


@dataclasses.dataclass(frozen=True, slots=True)
class CitationConfig:
    external_api_url: str
    connected_root_id: str | None = None
    external_account_id: str | None = None


class ItemType(StrEnum):
    DOCUMENT = auto()
    COLLECTION = auto()


@dataclasses.dataclass(slots=True)
class ItemResult:
    item_id: str
    item_name: str
    item_type: ItemType
    item_path: list[str] | None = None
    can_be_root: bool = None
    may_contain_root_candidates: bool = None
    csl: dict | None = None

    def __post_init__(self):
        """By default can_be_root and may_contain_root_candidates are bound to item_type"""
        if self.can_be_root is None:
            self.can_be_root = self.item_type == ItemType.COLLECTION
        if self.may_contain_root_candidates is None:
            self.may_contain_root_candidates = self.item_type == ItemType.COLLECTION


@dataclasses.dataclass(slots=True)
class ItemSampleResult:
    items: list[ItemResult]
    total_count: int | None = None
    next_sample_cursor: str | None = None
    prev_sample_cursor: str | None = None


# TODO: Merge My library and documents pickers into one picker (Zotero)
# TODO: Migrate CSL compilation to backend


class CitationServiceInterface(BaseAddonInterface):
    @immediate_operation(capability=AddonCapabilities.ACCESS)
    def list_root_collections(self) -> ItemSampleResult:
        """Lists directories (or collections) inside root"""

    @immediate_operation(capability=AddonCapabilities.ACCESS)
    def list_collection_items(
        self, collection_id: str, filter_items: ItemType | None = None
    ) -> ItemSampleResult:
        """Lists directories (or collections) and sources (books) inside root"""

    @immediate_operation(capability=AddonCapabilities.ACCESS)
    def get_item_info(self, item_id: str) -> ItemResult:
        """Lists directories (or collections) and sources (books) inside root"""


@dataclasses.dataclass(frozen=True)
class CitationAddonImp(AddonImp):
    """base class for storage addon implementations"""

    ADDON_INTERFACE = CitationServiceInterface

    config: CitationConfig
    network: HttpRequestor
