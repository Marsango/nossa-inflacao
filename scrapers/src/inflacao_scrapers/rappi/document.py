"""Read exact embedded JSON and validate public Rappi source locations."""

import re
from html.parser import HTMLParser
from urllib.parse import urlsplit

from ..vtex.json import decode_response

ORIGIN = "https://www.rappi.com.br"


class NextData(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=False)
        self.active = False
        self.documents = []
        self.product_urls = {}
        self.feed(source)

    def handle_starttag(self, tag, attributes):
        if tag == "script" and dict(attributes).get("id") == "__NEXT_DATA__":
            self.active = True
            self.documents.append("")
        if tag == "a":
            self.record_product_url(dict(attributes).get("href", ""))

    def record_product_url(self, value):
        path = value.removeprefix(ORIGIN)
        match = re.fullmatch(r"/p/[a-z0-9-]+-([1-9]\d*)", path)
        if match:
            self.product_urls[match[1]] = ORIGIN + path

    def handle_data(self, data):
        if self.active:
            self.documents[-1] += data

    def handle_endtag(self, tag):
        if tag == "script":
            self.active = False


def page_document(source):
    documents = NextData(source).documents
    if len(documents) != 1:
        raise ValueError("Missing or ambiguous Rappi page data; possible block or source change")
    document = decode_response(documents[0])
    properties = document.get("props", {}).get("pageProps")
    if not isinstance(properties, dict) or not isinstance(properties.get("fallback"), dict):
        raise ValueError("Missing Rappi page properties or fallback data")
    return document, properties


def product_urls(source):
    return NextData(source).product_urls


def public_url(value):
    parts = urlsplit(value)
    if parts.scheme != "https" or parts.netloc != "www.rappi.com.br":
        raise ValueError("Expected the public HTTPS Rappi Brazil host")
    if parts.query or parts.fragment or "%" in parts.path:
        raise ValueError("Rappi inspection URLs must have canonical paths without query/fragment")
    if not re.fullmatch(r"/(?:[a-z0-9-]+/)?lojas/[a-zA-Z0-9/-]+", parts.path):
        raise ValueError("Expected a public Rappi directory or store path")
    if any(part in {".", "..", ""} for part in parts.path.strip("/").split("/")):
        raise ValueError("Invalid Rappi path")
    return value


def store_slug(value):
    if not isinstance(value, str) or not re.fullmatch(r"[1-9]\d*-[a-z0-9-]+", value):
        raise ValueError("Invalid Rappi branch URL identity")
    return value


def identity(value):
    if type(value) is int and value > 0:
        return str(value)
    if isinstance(value, str) and re.fullmatch(r"[1-9]\d*", value):
        return value
    raise ValueError("Missing or malformed Rappi identifier")
