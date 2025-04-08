from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass

from django.core.exceptions import ValidationError

from addon_toolkit.interfaces.link import (
    ItemResult,
    ItemSampleResult,
    ItemType,
    LinkAddonHttpRequestorImp,
)


DATAVERSE_REGEX = re.compile(r"^dataverse/(?P<id>\d*)$")
DATASET_REGEX = re.compile(r"^dataset/(?P<id>.*)$")


@dataclass
class DataverseLinkImp(LinkAddonHttpRequestorImp):
    """storage on dataverse

    see https://guides.dataverse.org/en/latest/api/native-api.html
    """

    async def build_url_for_id(self, item_id: str) -> str:
        dataset_id = DATASET_REGEX.match(item_id)["id"]
        dataset = await self._fetch_dataset(dataset_id)
        return dataset.item_id

    async def get_external_account_id(self, _: dict[str, str]) -> str:
        try:
            async with self.network.GET("api/v1/users/:me") as response:
                if not response.http_status.is_success:
                    raise ValidationError(
                        "Could not get dataverse account id, check your API Token"
                    )
                content = await response.json_content()
                return content.get("data", {}).get("id")
        except ValueError as exc:
            if "relative url may not alter the base url" in str(exc).lower():
                raise ValidationError(
                    "Invalid host URL. Please check your Dataverse base URL."
                )
            raise

    async def list_root_items(self, page_cursor: str = "") -> ItemSampleResult:
        async with self.network.GET(
            "api/mydata/retrieve",
            query=[
                ["selected_page", page_cursor],
                *[("role_ids", role) for role in range(1, 9)],
                ("dvobject_types", "Dataverse"),
                *[
                    ("published_states", state)
                    for state in [
                        "Unpublished",
                        "Published",
                        "Draft",
                        "Deaccessioned",
                        "In+Review",
                    ]
                ],
            ],
        ) as response:
            content = await response.json_content()
            if resp_data := content.get("data"):
                return parse_mydata(resp_data)
            return ItemSampleResult(items=[], total_count=0)

    async def get_item_info(self, item_id: str) -> ItemResult:
        if not item_id:
            return ItemResult(item_id="", item_name="", item_type=ItemType.FOLDER)
        elif match := DATAVERSE_REGEX.match(item_id):
            entity = await self._fetch_dataverse(match["id"])
        elif match := DATASET_REGEX.match(item_id):
            entity = await self._fetch_dataset(persistent_id=match["id"])
        else:
            raise ValueError(f"Invalid item id: {item_id}")

        return entity

    async def list_child_items(
        self,
        item_id: str,
        page_cursor: str = "",
        item_type: ItemType | None = None,
    ) -> ItemSampleResult:
        if not item_id:
            return await self.list_root_items(page_cursor)
        elif match := DATAVERSE_REGEX.match(item_id):
            items = await self._fetch_dataverse_items(match["id"])
            return ItemSampleResult(
                items=items,
                total_count=len(items),
            )
        else:
            return ItemSampleResult(items=[], total_count=0)

    async def _fetch_dataverse_items(self, dataverse_id) -> list[ItemResult]:
        async with self.network.GET(
            f"api/dataverses/{dataverse_id}/contents"
        ) as response:
            response_content = await response.json_content()
            return await asyncio.gather(
                *[
                    self.get_dataverse_or_dataset_item(item)
                    for item in response_content["data"]
                ]
            )

    async def get_dataverse_or_dataset_item(self, item: dict):
        match item["type"]:
            case "dataset":
                return await self._fetch_dataset(dataset_id=item["id"])
            case "dataverse":
                return parse_dataverse_as_subitem(item)
        raise ValueError(f"Invalid item type: {item['type']}")

    async def _fetch_dataverse(self, dataverse_id) -> ItemResult:
        async with self.network.GET(f"api/dataverses/{dataverse_id}") as response:
            return parse_dataverse(await response.json_content())

    async def _fetch_dataset(
        self, dataset_id: str = None, persistent_id: str = None
    ) -> ItemResult:
        url = f"api/datasets/{':persistentId' if persistent_id else dataset_id}"
        query = {"persistentId": persistent_id} if persistent_id else {}
        # async with self.network.GET("api/datasets/:persistentId/", query={'persistentId': dataset_id}) as response:
        async with self.network.GET(url, query=query) as response:
            return parse_dataset(await response.json_content())


###
# module-local helpers


def parse_dataverse_as_subitem(data: dict):
    return ItemResult(
        item_type=ItemType.FOLDER,
        item_name=data["title"],
        item_id=f'dataverse/{data["id"]}',
    )


def parse_dataverse(data: dict):
    if data.get("data"):
        data = data["data"]
    return ItemResult(
        item_type=ItemType.FOLDER,
        item_name=data["name"],
        item_id=f'dataverse/{data["id"]}',
    )


def parse_mydata(data: dict):
    if data.get("data"):
        data = data["data"]
    return ItemSampleResult(
        items=[
            ItemResult(
                item_id=f"dataverse/{file['entity_id']}",
                item_name=file["name"],
                item_type=ItemType.FOLDER,
            )
            for file in data["items"]
        ],
        total_count=data["total_count"],
        next_sample_cursor=(
            data["pagination"]["nextPageNumber"]
            if data["pagination"]["hasNextPageNumber"]
            else None
        ),
    )


def parse_dataset(data: dict) -> ItemResult:
    if data.get("data"):
        data = data["data"]
    try:
        return ItemResult(
            item_id=f'dataset/{data['latestVersion']["datasetPersistentId"]}',
            item_name=[
                item
                for item in data["latestVersion"]["metadataBlocks"]["citation"][
                    "fields"
                ]
                if item["typeName"] == "title"
            ][0]["value"],
            item_type=ItemType.FOLDER,
        )
    except (KeyError, IndexError) as e:
        raise ValueError(f"Invalid dataset response: {e=}")
