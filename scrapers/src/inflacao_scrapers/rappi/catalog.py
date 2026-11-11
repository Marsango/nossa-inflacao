"""Bind visible product sections to their public branch; previews never imply completeness."""

from dataclasses import dataclass
from urllib.parse import urlsplit

from .document import identity, page_document, product_urls, public_url, store_slug

RESPONSES = ("store_home_response", "sub_aisles_response", "aisle_detail_response")


@dataclass(frozen=True)
class Storefront:
    branch: dict
    products: list[dict]
    membership_required: bool | None
    advertised_products: int | None
    category_paths: list[str]
    warnings: list[str]
    product_urls: dict[str, str]

    def coverage(self):
        return {
            "complete": False, "kind": "public page preview",
            "displayed_products": len(self.products),
            "advertised_category_products": self.advertised_products,
            "category_paths": self.category_paths,
        }


def parse_storefront(source, source_url, expected_store_id=None):
    document, properties = page_document(source)
    path = urlsplit(public_url(source_url)).path.split("/lojas/", 1)[1]
    slug = store_slug(path.split("/", 1)[0])
    if document.get("query", {}).get("friendly_url") != slug:
        raise ValueError("Rappi document points to another branch")
    entry = properties["fallback"].get("storefront/" + path)
    if not isinstance(entry, dict):
        raise ValueError("Rappi data does not match the requested branch/category path")
    response = primary_response(entry)
    context = response.get("context_info", {})
    branch = validated_branch(context.get("store"), slug, expected_store_id)
    return Storefront(
        branch, displayed_products(response, branch), mandatory_membership(context),
        advertised_count(entry), category_paths(entry, slug),
        ["Public Rappi preview; complete catalog traversal and freshness unverified."],
        product_urls(source),
    )


def primary_response(entry):
    responses = [entry[key].get("data") for key in RESPONSES if key in entry]
    if len(responses) != 1 or not isinstance(responses[0], dict):
        raise ValueError("Missing or ambiguous Rappi storefront response")
    if not isinstance(responses[0].get("components"), list):
        raise ValueError("Missing Rappi product sections")
    return responses[0]


def validated_branch(branch, slug, expected_store_id):
    if not isinstance(branch, dict):
        raise ValueError("Missing Rappi branch context")
    store_id = identity(branch.get("store_id"))
    if store_id != slug.split("-", 1)[0]:
        raise ValueError("Rappi branch context differs from requested URL")
    if expected_store_id is not None and store_id != expected_store_id:
        raise ValueError("Rappi branch differs from the expected store")
    if not isinstance(branch.get("name"), str) or not branch["name"].strip():
        raise ValueError("Missing Rappi branch name")
    return branch


def displayed_products(response, branch):
    products = {}
    for component in response["components"]:
        resource = component.get("resource", {})
        add_products(products, resource.get("products", []), branch)
    if not products:
        raise ValueError("Empty Rappi preview requires verification; no products parsed")
    return list(products.values())


def add_products(products, entries, branch):
    if not isinstance(entries, list):
        raise ValueError("Malformed Rappi product list")
    for product in entries:
        add_product(products, product, branch)


def add_product(products, product, branch):
    product_id = identity(product.get("product_id"))
    if identity(product.get("store_id")) != identity(branch["store_id"]):
        raise ValueError("Rappi product belongs to another branch")
    previous = products.get(product_id)
    if previous is not None and previous != product:
        raise ValueError("Conflicting Rappi product previews; price/context changed")
    products[product_id] = product


def mandatory_membership(context):
    fidelity = context.get("fidelity") or {}
    if fidelity.get("is_mandatory") is True:
        return True
    return None


def advertised_count(entry):
    extras = entry.get("aisle_detail_response_extras", {})
    selected = extras.get("subaisle", {}).get("id")
    categories = extras.get("aisle", {}).get("categories", [])
    counts = [
        category.get("product_count") for category in categories if category["id"] == selected
    ]
    if len(counts) == 1 and type(counts[0]) is int and counts[0] >= 0:
        return counts[0]
    return None


def category_paths(entry, slug):
    components = entry.get("aisles_tree_response", {}).get("components", [])
    resources = [component.get("resource", {}) for component in components]
    paths = [resource.get("friendly_url") for resource in resources]
    return list(dict.fromkeys(
        urlsplit(public_url("https://www.rappi.com.br/lojas/" + slug + "/" + path)).path
        for path in paths if isinstance(path, str) and path
    ))
