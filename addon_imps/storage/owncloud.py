import xml.etree.ElementTree as ET
from urllib.parse import (
    unquote,
    urlparse,
)

from rest_framework.exceptions import ValidationError

from addon_toolkit.interfaces import storage
from addon_toolkit.interfaces.storage import ItemType


_BUILD_PROPFIND_CURRENT_USER_PRINCIPAL = """<?xml version="1.0" encoding="UTF-8"?>
<d:propfind xmlns:d="DAV:">
    <d:prop>
        <d:current-user-principal/>
    </d:prop>
</d:propfind>"""

_BUILD_PROPFIND_DISPLAYNAME = """<?xml version="1.0" encoding="UTF-8"?>
<d:propfind xmlns:d="DAV:">
    <d:prop>
        <d:displayname/>
    </d:prop>
</d:propfind>"""

_BUILD_PROPFIND_ALLPROPS = """<?xml version="1.0" encoding="UTF-8"?>
<d:propfind xmlns:d="DAV:">
    <d:allprop/>
</d:propfind>"""


class OwnCloudStorageImp(storage.StorageAddonHttpRequestorImp):
    async def get_external_account_id(self, auth_result_extras: dict[str, str]) -> str:
        try:
            headers = {
                "Depth": "0",
            }
            async with self.network.PROPFIND(
                uri_path=self._strip_absolute_path(""),
                headers=headers,
                content=_BUILD_PROPFIND_CURRENT_USER_PRINCIPAL,
            ) as response:
                if response.http_status in (401, 403):
                    raise ValidationError(
                        "Invalid OwnCloud credentials (unauthorized)."
                    )
                response_xml = await response.text_content()
                try:
                    current_user_principal_url = self._parse_current_user_principal(
                        response_xml
                    )
                except ValueError:
                    username = (
                        auth_result_extras.get("username") or self._fallback_username
                    )
                    if not username:
                        raise ValueError(
                            "Username is required for fallback but not provided."
                        )
                    current_user_principal_url = f"/remote.php/dav/files/{username}/"
                except ET.ParseError:
                    raise ValidationError(
                        "Please check base url, as it doesn't point to a valid owncloud deployment"
                    )

            current_user_principal_url = current_user_principal_url.lstrip("/")

            async with self.network.PROPFIND(
                uri_path=self._strip_absolute_path(current_user_principal_url),
                headers=headers,
                content=_BUILD_PROPFIND_DISPLAYNAME,
            ) as response:
                if response.http_status in (401, 403):
                    raise ValidationError(
                        "Invalid OwnCloud credentials (unauthorized)."
                    )
                response_xml = await response.text_content()
                return self._parse_displayname(response_xml)
        except ValueError as exc:
            if "relative url may not alter the base url" in str(exc).lower():
                raise ValidationError(
                    "Invalid host URL. Please check your OwnCloud base URL."
                )
            raise

    @property
    def _fallback_username(self) -> str | None:
        return "default-username"

    async def list_root_items(self, page_cursor: str = "") -> storage.ItemSampleResult:
        root_item = storage.ItemResult(
            item_id=_owncloud_root_id(),
            item_name="Root Directory",
            item_type=ItemType.FOLDER,
            can_be_root=True,
            may_contain_root_candidates=True,
        )
        return storage.ItemSampleResult(items=[root_item])

    async def get_item_info(self, item_id: str) -> storage.ItemResult:
        item_type, path = _parse_item_id(item_id)
        url = self._strip_absolute_path(path)

        headers = {
            "Depth": "0",
        }

        async with self.network.PROPFIND(
            uri_path=url,
            headers=headers,
            content=_BUILD_PROPFIND_ALLPROPS,
        ) as response:
            response_xml = await response.text_content()
            root = ET.fromstring(response_xml)
            response_element = root.find(
                "d:response", {"d": "DAV:", "oc": "http://owncloud.org/ns"}
            )
            if response_element is None:
                raise ValueError("No response element found in PROPFIND response")
            item_result = self._parse_response_element(response_element, path)
            return item_result

    async def list_child_items(
        self,
        item_id: str,
        page_cursor: str = "",
        item_type: storage.ItemType | None = None,
    ) -> storage.ItemSampleResult:
        _item_type, path = _parse_item_id(item_id)
        relative_path = self._strip_absolute_path(path)
        headers = {
            "Depth": "1",
        }

        async with self.network.PROPFIND(
            uri_path=relative_path,
            headers=headers,
            content=_BUILD_PROPFIND_ALLPROPS,
        ) as response:
            response_xml = await response.text_content()
            root = ET.fromstring(response_xml)
            items = []
            ns = {"d": "DAV:", "oc": "http://owncloud.org/ns"}
            for response_element in root.findall("d:response", ns):
                href_element = response_element.find("d:href", ns)
                if href_element is None or not href_element.text:
                    continue
                href = href_element.text
                item_path = self._href_to_path(href)

                if item_path.rstrip("/") == path.rstrip("/"):
                    continue

                item_result = self._parse_response_element(response_element, item_path)
                if item_type is not None and item_result.item_type != item_type:
                    continue
                items.append(item_result)

            return storage.ItemSampleResult(items=items)

    def _strip_absolute_path(self, path: str) -> str:
        return path.lstrip("/")

    async def build_wb_config(self) -> dict:
        base_url = self.config.external_api_url.rstrip("/")
        parsed_url = urlparse(base_url)

        root_host = f"{parsed_url.scheme}://{parsed_url.netloc}"
        folder_path = ""

        if self.config.connected_root_id:
            _, subpath = _parse_item_id(self.config.connected_root_id)
            folder_path = subpath.strip("/")

        return {
            "folder": folder_path,
            "host": root_host,
            "verify_ssl": True,
        }

    def _parse_response_element(
        self, response_element: ET.Element, path: str
    ) -> storage.ItemResult:
        ns = {"d": "DAV:", "oc": "http://owncloud.org/ns"}
        resourcetype = response_element.find(".//d:resourcetype", ns)
        item_type = (
            storage.ItemType.FOLDER
            if resourcetype is not None
            and resourcetype.find("d:collection", ns) is not None
            else storage.ItemType.FILE
        )
        displayname_element = response_element.find(".//d:displayname", ns)
        displayname = (
            displayname_element.text
            if displayname_element is not None and displayname_element.text
            else path.rstrip("/").split("/")[-1]
        )
        return storage.ItemResult(
            item_id=_make_item_id(item_type, path),
            item_name=displayname,
            item_type=item_type,
        )

    def _parse_current_user_principal(self, response_xml: str) -> str:
        return self._parse_property(
            response_xml,
            xpath=".//d:current-user-principal/d:href",
            error_message="current-user-principal not found in response",
        )

    def _parse_displayname(self, response_xml: str) -> str:
        try:
            return self._parse_property(
                response_xml,
                xpath=".//d:displayname",
                error_message="displayname not found in response",
            )
        except ValueError:
            return "default-name"

    def _parse_property(self, response_xml: str, xpath: str, error_message: str) -> str:
        ns = {"d": "DAV:"}
        root = ET.fromstring(response_xml)
        element = root.find(xpath, ns)
        if element is not None and element.text:
            return element.text
        else:
            raise ValueError(error_message)

    def _href_to_path(self, href: str) -> str:
        parsed_href = urlparse(unquote(href))
        href_path = parsed_href.path.lstrip("/")

        base_path = urlparse(self.config.external_api_url).path.rstrip("/").lstrip("/")
        if href_path.startswith(base_path):
            # fmt: off
            path = href_path[len(base_path):]
        else:
            path = href_path

        path = path.strip("/")
        return path or "/"


def _make_item_id(item_type: storage.ItemType, path: str) -> str:
    return f"{item_type.value}:{path}"


def _parse_item_id(item_id: str) -> tuple[storage.ItemType, str]:
    if not item_id:
        return ItemType.FOLDER, "/"
    _type, _path = item_id.split(":", maxsplit=1)
    return storage.ItemType(_type), _path


def _owncloud_root_id() -> str:
    return _make_item_id(storage.ItemType.FOLDER, "/")
