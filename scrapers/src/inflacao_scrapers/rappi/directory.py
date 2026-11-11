"""Discover displayed supermarket branches and skip implemented retailer families."""

from dataclasses import dataclass

from ..scope import normalize
from .document import ORIGIN, identity, page_document, public_url, store_slug

IMPLEMENTED_NAMES = {
    "super muffato": "super-muffato", "muffato": "super-muffato", "angeloni": "angeloni",
    "festval": "festval", "mambo": "mambo", "supermercados mambo": "mambo",
    "hirota": "hirota", "nagumo": "nagumo", "sonda": "sonda", "atacadao": "atacadao",
}


@dataclass(frozen=True)
class Directory:
    location: str | None
    branches: list[dict]
    cities: list[dict]

    def report(self, include_existing=False):
        branches = [entry for entry in self.branches if not entry["existing_adapter"]]
        if include_existing:
            branches = self.branches
        return {
            "location": self.location, "coverage": "displayed branches; not a national census",
            "branches": branches, "cities": self.cities,
            "excluded_branches": sum(bool(entry["existing_adapter"]) for entry in self.branches),
            "retailer_names": sorted({entry["retailer"] for entry in branches}),
        }


def implemented_retailer(name, adapters=None):
    if adapters is None:
        from ..adapters.registry import ADAPTERS

        adapters = ADAPTERS
    normalized = normalize(name)
    adapter = IMPLEMENTED_NAMES.get(normalized)
    if normalized.startswith("carrefour"):
        adapter = "carrefour"
    if normalized.startswith("pao de acucar"):
        adapter = "pao-de-acucar"
    return adapter if adapter in adapters else None


def parse_directory(source):
    _, properties = page_document(source)
    groups = directory_groups(properties["fallback"])
    branches = {}
    for group in groups:
        add_group(branches, group)
    if not branches:
        raise ValueError("Rappi supermarket directory has no branch entries")
    location = properties.get("commonData", {}).get("currentLocation")
    return Directory(location, list(branches.values()), city_links(properties))


def directory_groups(fallback):
    groups = [value["storeGroups"] for value in fallback.values() if "storeGroups" in value]
    if len(groups) != 1 or not isinstance(groups[0], list):
        raise ValueError("Missing or ambiguous Rappi supermarket groups")
    return groups[0]


def add_group(branches, group):
    title = group.get("title")
    if not isinstance(title, str) or not isinstance(group.get("stores"), list):
        raise ValueError("Malformed Rappi supermarket group")
    for entry in group["stores"]:
        add_branch(branches, entry, title)


def add_branch(branches, source, group):
    branch = directory_branch(source, group)
    key = branch["store_id"]
    previous = branches.get(key)
    if previous is None:
        branches[key] = branch
        return
    if previous["url"] != branch["url"] or previous["retailer"] != branch["retailer"]:
        raise ValueError("Conflicting Rappi directory branch identity")
    previous["groups"] = list(dict.fromkeys([*previous["groups"], group]))


def directory_branch(source, group):
    name = source.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Missing Rappi retailer name")
    slug = store_slug(source.get("friendlyURL"))
    store_id = identity(source.get("storeId"))
    if slug.split("-", 1)[0] != store_id:
        raise ValueError("Rappi directory branch ID differs from its URL")
    return {
        "retailer": name, "store_id": store_id, "store_type": source.get("storeType"),
        "url": ORIGIN + "/lojas/" + slug, "groups": [group],
        "existing_adapter": implemented_retailer(name), "catalog_verified": False,
    }


def city_links(properties):
    return [
        {"name": entry["name"], "url": public_url(ORIGIN + entry["url"])}
        for entry in properties.get("cityURLs", [])
    ]
