"""Conservative product facts; legacy availability and approximate weights are not inferred."""

from ..models import Product
from ..models.product import validate_gtin
from ..packaging import package_metadata
from ..packaging.resolution import reconcile
from .document import identity


def product_name(source):
    name = source.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Missing Rappi product name")
    return name


def availability(source):
    flags = (source.get("in_stock"), source.get("is_available"))
    if source.get("is_discontinued") is True or source.get("discontinued") is True:
        return "out_of_stock"
    if any(type(flag) is not bool for flag in flags):
        return "unknown"
    if source.get("possibly_out_of_stock") or source.get("is_possible_stockout"):
        return "unknown"
    if flags == (True, True):
        return "in_stock"
    if flags == (False, False):
        return "out_of_stock"
    return "unknown"


def product_details(source, warnings):
    name = product_name(source)
    package = None
    if source.get("sale_type") == "U":
        package = package_details(source, warnings)
    return Product(
        source_product_id=identity(source.get("product_id")), name=name,
        brand=brand(source), gtin=source_gtin(source.get("ean"), warnings), package=package,
    )


def package_details(source, warnings):
    import re

    presentation = source.get("presentation") or ""
    count = re.match(r"\s*(\d+)\s*[x×]\s*", presentation, re.I)
    if count and count[1] != "1":
        warnings.append("Multipack presentation unverified; package contents omitted")
        return None
    presentation = re.sub(r"^\s*1\s*[x×]\s*", "", presentation, flags=re.I)
    packages = [package_metadata(text, warnings) for text in (product_name(source), presentation)]
    try:
        return reconcile([package for package in packages if package is not None])
    except ValueError:
        warnings.append("Conflicting Rappi name/presentation; package contents omitted")
        return None


def brand(source):
    value = source.get("trademark")
    if value in (None, "", "Sem Trademark"):
        return None
    if not isinstance(value, str):
        raise ValueError("Malformed Rappi brand")
    return value


def source_gtin(value, warnings):
    if value in (None, ""):
        return None
    try:
        validate_gtin(value)
        return value
    except (ValueError, AttributeError, TypeError):
        warnings.append("Invalid Rappi barcode omitted; source product ID retained")
        return None
