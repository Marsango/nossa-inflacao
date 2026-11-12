# Shop collectors

The registered adapters collect public VTEX catalogs for **Super Muffato,
Angeloni, and Festval** around Curitiba, plus **Mambo** delivery and **Hirota**
Nazaré pickup and **Pão de Açúcar** Ricardo Jafet delivery in São Paulo/SP.
The default schedule also includes Pão de Açúcar in ten additional capitals and
Angeloni Beira Mar delivery in Florianópolis/SC; see [capital contexts](#additional-capital-contexts).
Atacadão has independently scheduled online branch catalogs in 22 capitals;
see [Atacadão capital branches](#atacadão-capital-branches) for coverage and blockers.
Carrefour has verified delivery-region catalogs in 13 capitals; see
[Carrefour delivery collection](#carrefour-delivery-collection).
GBarbosa uses its own regional VTEX catalog in Aracaju, Salvador and Maceió;
see [GBarbosa delivery collection](#gbarbosa-delivery-collection).
Hirota and Pão de Açúcar use their own public APIs. Sonda reads its public HTML catalog with fulfillment context explicitly unknown;
see [São Paulo setup, evidence and limitations](../docs/plans/sao-paulo-retailers.md).
The core supplies brand-independent
monitoring targets through its authenticated scope endpoint. Migration 00006
seeds 16 targets covering the DIEESE basket's 13 food groups, regional flour/sugar
variants, and pasta. Migrations 00007–00010 expand the scope to **96 targets**,
including eggs, chicken, more meat cuts, produce, dairy, pantry foods, hygiene,
cleaning products, sweets, snacks, soft drinks, and processed meats.
See the [basket scope and sources](../docs/contracts/monitoring/v1/basic-food-basket.md)
and the [latest additions, activation steps, and coverage limits](../docs/contracts/monitoring/v1/snacks-and-convenience.md).
Variable-weight meat, produce and bakery items still require adapter support;
the seed does not make their collection complete. Matching brands, variants and
package sizes stay separate products.
These groups are not a statistically representative inflation basket.

| Adapter | Verified context | Discovery |
| --- | --- | --- |
| `super-muffato` | Champagnat online branch, sales channel `8`; no CEP selected | Paginated target searches |
| `angeloni` | Delivery catalog for CEP `80730201`, mapped to Angeloni Bigorrilho | Catalog category browsing, filtered by core targets |
| `festval` | Delivery catalog for CEP `80730201`, mapped to regional seller `meufestvaldark` | Paginated target searches on sales channel `2` |
| `hirota` | Pickup at Avenida Nazaré 1299, CEP `04263100`, organization 171, filial 1, distribution center 1 | Department browsing filtered by core scope; diagnostic discovery samples the public best sellers |
| `mambo` | Delivery catalog for São Paulo CEP `01310200`, mapped to regional seller `mambodelivery215`; packaged products and advertised kg prices with portions up to 3 kg | Paginated target searches on sales channel `1` |
| `nagumo` | Vila Curuçá pickup, São Paulo/SP, store `13`, branch CEP `08030040` | Public HTTP searches filtered by core targets; ordinary/member offers and advertised kg prices |
| `atacadao` | Explicit branch and seller, independently verified every run; online catalogs in 22 capitals | Public FastStore target searches; regular, wholesale and advertised kg offers |
| `carrefour` | Verified delivery CEP and region in 13 capitals | Isolated browser sessions; regular, bulk and advertised kg offers |
| `gbarbosa` | Verified delivery CEP and local grocery seller in Aracaju, Salvador and Maceió | Public VTEX target searches; packaged and advertised kg prices |

The regional VTEX delivery adapters resolve their configured CEP through the public regions
endpoint at the start of every run. The response must contain the configured
`regional_seller_id`; a missing/ambiguous mapping stops that scraper before price
collection. The resolved region is sent explicitly in the request and public
VTEX segment cookie. Observations preserve CEP, city/state, `channel=delivery`,
and `store_id=region:<resolved region>/seller:<regional seller>`. The price
response's seller ID remains `1`; it is preserved separately in `seller_id`.
This records a regional online catalog; checkout prices and physical shelf prices
require separate verification. Muffato's current context remains `online`, with
a null CEP.

## Setup

Run from `scrapers/`, with Python 3.12 or newer:

```sh
python3 -m venv .venv
.venv/bin/pip install --no-cache-dir -e '.[dev]'
cp scrapers.example.toml config.toml
```

This makes the Python package and `inflacao-scraper` command available inside
the local virtual environment. Editable mode (`-e`) uses source changes directly;
`[dev]` adds pytest and Ruff. No service, scheduler, browser, or system-wide
installation is needed. Database access is not part of scraper operation or tests.

Hirota and Carrefour additionally require Chrome/Chromium and the optional browser packages:

```sh
.venv/bin/pip install -e '.[browser]'
.venv/bin/inflacao-scraper --config hirota.example.toml discover --query leite --limit 1
.venv/bin/pytest tests/hirota/test_live.py --live -q
```

The browser initializes a fresh anonymous storefront session once per run. There
is no customer login or saved profile. Session headers stay in memory, outside
configuration serialization and spool payloads. API requests then use the shared
HTTP pacing/retry policy. Only the verified Nazaré pickup context is accepted;
missing/changed branch data stops collection. Browser caching, exports and task
retries are disabled. Set `chrome_executable_path` only if automatic browser
selection fails. The deployment image includes Chromium and the pinned browser
runtime. HTTP-only adapters do not launch a browser. See
[Hirota evidence and supported formats](../docs/evidence/hirota-onboarding.md).

Nagumo uses HTTP only, with a fresh anonymous session and explicit selection of
Vila Curuçá pickup on every run. No browser extra or customer login is required:

```sh
.venv/bin/inflacao-scraper --config nagumo.example.toml discover --query leite --limit 1
.venv/bin/pytest tests/nagumo/test_live.py --live -q
```

The adapter checks the selected branch after every price page. Ordinary and
Meu Nagumo member prices stay separate; variable-weight offers use advertised
kg prices without a fixed package inferred from portions. See
[Nagumo setup, source evidence and limits](../docs/plans/nagumo-retailer.md).

`config.toml` and `data/` are ignored by Git. Set a unique `scraper_id` for each
independent installation. Keep the ingestion token only in the environment.

## Shared runner and adapter registration

The same command runs every enabled entry in `config.toml`:

```sh
.venv/bin/inflacao-scraper --config config.toml collect
```

Use one `[[scrapers]]` table per shop/store configuration. Each table has its own
adapter, scraper/shop identity, core URL, request settings, branch selection,
and fallback spool. The adapter name selects an implementation from
[`ADAPTERS`](src/inflacao_scrapers/adapters/registry.py). Muffato, Angeloni,
Festval, Mambo, Hirota, Pão de Açúcar, Sonda, Nagumo, Atacadão and Carrefour
are registered and enabled in the default schedule configuration in
[`scrapers.example.toml`](scrapers.example.toml). Individual configurations are in
[`angeloni.example.toml`](angeloni.example.toml),
[`festval.example.toml`](festval.example.toml), and
[`muffato.example.toml`](muffato.example.toml). Mambo has a
[standalone example](mambo.example.toml) and a
[São Paulo runner example](sao-paulo.example.toml); all five São Paulo collectors
are enabled by default. See [Sonda setup and limits](../docs/plans/sonda-retailer.md). For example:

```toml
[runner]
max_workers = 2

[[scrapers]]
adapter = "super-muffato"
enabled = true
scraper_id = "local-collector"
core_url = "http://127.0.0.1:8080"
ingestion_token_env = "INGESTION_TOKEN"
sales_channel = "8"
store_id = "sales-channel:8"
city = "Curitiba"
state = "PR"

[[scrapers]]
adapter = "another-shop"
enabled = false
# After registering this adapter, add its required settings and enable it.
```

Collection and delivery run with at most two worker threads by default. Set
`[runner].max_workers` to an integer from `1` to `8`; `1` restores sequential
execution. Existing runner configurations without this table use two workers.
Single-scraper configurations keep their original format. Discovery and status
remain sequential so their output stays ordered.

Each enabled scraper gets a new HTTP client and cookie jar, request pacing state,
run ID, listing-deduplication state, observation spool and diagnostic spool.
Browser adapters share a separate one-session limit covering creation through
cleanup, protecting Botasaurus's process-wide driver/profile state. Each browser
session still uses a fresh profile; HTTP work can overlap it. A worker waiting for
that browser limit counts toward `max_workers`. Browser-heavy schedules therefore
benefit less than API schedules. Request pacing and retries stay local to each
entry; several contexts of one retailer can make requests concurrently.

A collection or delivery failure stops that scraper; the runner continues with
other entries and waits for every result. The final summary reports the number of
scrapers and failures, and the command exits nonzero if any scraper failed.
Logs include schedule IDs, run IDs and per-entry elapsed time. Shared pipeline log
lines are written atomically; messages from different entries can appear in any
order. An interrupted run cancels queued entries and waits for active workers to
release their clients, queues and browsers.
Unknown enabled adapters, invalid settings, and conflicting spool paths fail
configuration validation before any scraper starts. Disabled entries require
only `adapter` and `enabled = false`; their adapters need not be installed.
All-disabled configurations are a successful no-op.

The deployment runtime smoke compares one and two workers with six paced HTTP
fixtures and two fresh Chromium sessions, without contacting retailers or a core.
It checks cookie/profile isolation and browser cleanup, and reports elapsed time,
CPU seconds, summed process RSS and file descriptors. In an environment with
pytest and Testcontainers installed, run from the repository root:

```sh
docker build -f deployment/scrapers.Dockerfile -t nossa-inflacao-scrapers:verify .
python -m pytest deployment/tests/test_scraper_browser.py -k parallel_runner -q -s
```

Summed RSS includes shared pages more than once; it is not container memory usage.
Use container metrics during representative collection before increasing workers
on a VPS. This offline fixture does not estimate live retailer throughput.

`ingestion_token_env` names the environment variable containing that scraper's
core token; it defaults to `INGESTION_TOKEN`. Tokens stay out of TOML files and
shop requests. The current core authorizes one `INGESTION_SCRAPER_ID` and a set of
`INGESTION_SHOP_IDS`; entries sending to the same core must use that authorized
scraper identity and token, with each shop registered and allowed. Separate core
instances can have different identities and token environment variables.

Runner entries default to `data/<shop_id>/<scraper_id>/spool.sqlite3`, relative to
the configuration file. Set distinct `spool_path` values explicitly when several
entries use the same shop and scraper identity. `deliver`, `status`, and diagnostic
`discover` also run across all enabled entries using their own settings.

Existing flat Muffato TOML files still work, default to `adapter = "super-muffato"`,
and retain `data/spool.sqlite3`. When migrating an existing queue to `[[scrapers]]`,
retain its explicit `spool_path`; the new example does this for Muffato.

To add a shop without changing the runner:

1. Implement pure parsing and bounded fetching in its own package. Subclass the
   shared `Settings` model for that shop's required options.
2. Define an [`Adapter`](src/inflacao_scrapers/adapters/__init__.py) with its name,
   settings model, `search_pages(requester, settings, target, query)`, and
   `discover(requester, settings, query, limit)` functions. Searches yield shared
   `ParsedPage` instances containing validated observations, fatal parsing issues,
   and nonfatal metadata warnings.
   An optional `prepare` callback resolves per-run context. An adapter that browses
   a whole catalog supplies `catalog_pages(requester, settings, scope)` instead
   of `search_pages`; the runner counts matches for every core target.
   Use fresh observation IDs/timestamps and report incomplete pagination as errors.
3. Import its adapter into `adapters/registry.py` and add it to `ADAPTERS` under
   its name. Registration is explicit; adding an unregistered Python file does
   not make it runnable.
4. Add an enabled `[[scrapers]]` table with that adapter's settings and authorize
   its identity/shop in the core. The existing `collect` command discovers the
   registration, collects its pages, and uses shared batching and delivery.

See [`muffato/adapter.py`](src/inflacao_scrapers/muffato/adapter.py) for the first
implementation. Adapter names are included in submitted collector provenance.

## Collection

```sh
.venv/bin/inflacao-scraper --config config.toml discover --query arroz --limit 50
# Start the core and export its matching INGESTION_TOKEN before collection.
.venv/bin/inflacao-scraper --config config.toml collect
.venv/bin/inflacao-scraper --config config.toml status
```

Discovery prints SKU IDs, names, package sizes, availability, and prices without
queueing measurements. It is an ad hoc diagnostic command, independent of the core.

For each enabled scraper, `collect` authenticates to `GET /api/v1/monitoring-targets`
once per run. Muffato and Festval search each target's phrases. They follow pagination, filter each
SKU using the central required/excluded name terms, and collects every matching
brand and individually sold package size. A SKU found by several queries or
targets is measured once per run. Brand and variant comparisons remain the core's
responsibility. See the [monitoring v1 contract](../docs/contracts/monitoring/v1/README.md).

Each page's validated observations are batched and sent directly to the core
before requesting another page. Successful delivery creates no local storage.
If delivery fails after bounded retries, the exact attempted batch is saved in
the scraper's configured spool and that scraper stops with a nonzero result. Use `deliver`
to retry saved batches; `collect` does not drain an existing backlog.
Every new measurement receives a new observation ID and UTC timestamp, even if
the price is unchanged. Run and submission IDs are printed for diagnosis. An
incomplete run exits nonzero; batches already accepted by the core remain there.
Restarting collection creates a new run. An interruption before a failed batch
is saved can lose that in-memory batch.

The core seeds the scope through migrations 00006–00010; add/refine targets with
forward migrations. Restart the updated core to apply pending migrations; the
daily scheduler receives the expanded scope on its next collection. Remove the
old `sku_ids` field from existing local TOML files.
`collect` now needs `INGESTION_TOKEN` and a reachable core. It never falls back to
a local product list if scope retrieval or validation fails. Credentials are sent
only to the configured core, never to shops; redirects are not followed.

The scraper reports unique matching listings per target. Missing targets, parser
errors, failed pages and repeated pagination mark the run incomplete. Searches
use 50 products per page and follow the source `resources` total when available;
otherwise a short/empty page ends the search. `max_search_pages` defaults to 50 per
query. Reaching that bound while more results may remain is an explicit failure.
An empty enabled scope is a successful no-op. Name filters are conservative:
missing type/processing details may exclude otherwise relevant products. Exhausting
search results does not prove complete retailer coverage.

Requests are synchronous, paced at one per second by default, with explicit
timeouts and at most three attempts for network failures, HTTP 429, and transient
500/502/503/504 responses. Retry-After is honored within the retry-time budget;
longer waits leave work for a later invocation. Redirects are not followed.
No collection-result cache is used. Requests ask for revalidation and use unique
query keys; responses with a positive HTTP Age are rejected as fresh measurements.
Prices can still reflect the shop's own upstream updates and indexing delays.

### Daily scheduling

`collect` runs once and exits. To keep collecting every day, activate the installed
virtual environment and start the scheduler from `scrapers/`:

```sh
source .venv/bin/activate
# Export the matching INGESTION_TOKEN before starting the scheduler.
python3 schedule.py
```

The default start time is **03:00 in America/Sao_Paulo**. Choose another daily
time or timezone with:

```sh
python3 schedule.py --at 08:00 --timezone America/Sao_Paulo
# Optional: use a different configuration file.
python3 schedule.py --config scrapers.example.toml --at 08:00
```

The script defaults to `config.toml` beside `schedule.py`, including when launched
from another directory. Installed packages also provide
`inflacao-scraper-schedule --config config.toml --at 08:00`; that command defaults
to the configuration in the working directory.

The scheduler prints its next start with a timezone offset and waits until that
time; starting it after today's scheduled time means the first run is tomorrow.
It reloads the configuration on every run and executes enabled scrapers with the
configured worker limit through the collection and automatic delivery pipeline.
Failures remain visible without ending the daily schedule. Saved failed batches
still require the existing `deliver` command for recovery.

Runs never overlap within one scheduler process. If collection extends beyond a
later scheduled time, that missed slot is skipped and the scheduler waits for
the next future daily time. There is no catch-up for time spent stopped.
Keep the machine awake. Press Ctrl+C to stop a foreground scheduler.

To run in the background and close the terminal, launch it with `nohup` from
`scrapers/`, after exporting the matching ingestion token:

```sh
mkdir -p data
nohup .venv/bin/python -u schedule.py --at 08:00 > data/scheduler.log 2>&1 < /dev/null &
echo $! > data/scheduler.pid
```

The process inherits the exported token. Output is written immediately to
`data/scheduler.log`. Start only one scheduler per configuration. Check its
process and follow its output with:

```sh
ps -p "$(cat data/scheduler.pid)" -o pid,etime,args
tail -f data/scheduler.log
```

Ctrl+C exits `tail` without stopping the scheduler. To stop the background
scheduler, verify the process above is the expected scheduler, then run:

```sh
kill "$(cat data/scheduler.pid)"
```

Background execution survives closing the terminal, but the machine must remain
running and awake. Restarting the machine stops scheduling; this command does
not install a service or start automatically at boot.

### Angeloni and Festval regionalization

The defaults use the public business-address CEP `80730201` in Bigorrilho. On
2026-10-29 the stores' public `GET /api/checkout/pub/regions` responses mapped
this CEP to `superangeloni24` (Angeloni Bigorrilho) and `meufestvaldark` (Festval).
These are delivery-region sellers, not pickup-point IDs. The regional mappings
are checked again on each invocation, rather than hardcoding a region token.
Changing the CEP requires verifying and configuring the matching regional seller.

Festval's homepage segment selected sales channel `2`. The adapter also preserves
the storefront's `utm_source=curitiba` segment field. Default unregionalized
search responses reported offers unavailable; applying the resolved regional
segment returned in-stock prices in live checks. The adapter never falls back
to an unregionalized price when resolving the configured context fails.

Angeloni's [published robots rules](https://super.angeloni.com.br/robots.txt)
exclude `ft`/`fq` keyword-filter URLs. Its adapter uses the public
`/_v/api/intelligent-search/product_search/<category facets>` catalog endpoint
with `count`, `page`, `sc`, and `regionId`. It uses no `ft`, `fq`, `query`, or `map`
query parameters. Each run loads the public category tree and automatically
discovers every available leaf category. Each category is traversed once for all
enabled core targets, then source names are filtered locally before parsing
offers. Only matching listings are submitted. Source pages are not replayed from
a previous run, and product overlap across categories is deduplicated.

**Adding a monitoring target is a core-only change.** Muffato and Festval search
the core's target queries; Angeloni scans the live catalog and applies the same
core rules. A new target or upstream category requires no scraper code or category
configuration changes. Collection still depends on retailer availability and the
adapter's supported source formats.

When upgrading an older configuration, remove `catalog_category_ids` to enable
automatic discovery and restart a running scheduler once to load the adapter
change. Future core target additions are fetched on the next run without a
scraper restart. The default and example configurations omit the restriction. An explicit
list such as `catalog_category_ids = [467]` remains available for bounded diagnostics;
it restricts coverage and can prevent new core targets from being found. Missing
selected categories, non-leaf selections, empty trees and truncated branches fail
explicitly. A broader scan increases requests and collection time, but stores only
matching observations.

VTEX rejects pages after page 50, so the adapter enforces that bound per category.
`max_catalog_pages` defaults to 1000 as an overall page budget across selected
categories. Reaching either bound, repeated pages, missing totals and prematurely
short pages are explicit incomplete runs. Already accepted batches remain in the core.
`discover` also browses Angeloni's configured categories, stopping after its requested number
of matching observations; use an individual config to inspect only one shop:

```sh
.venv/bin/inflacao-scraper --config angeloni.example.toml discover --query leite --limit 5
.venv/bin/inflacao-scraper --config festval.example.toml discover --query arroz --limit 5
```

Shared fetching, parsing, pagination and regionalization now live in `vtex/`.
Saved fixtures cover both response formats; Angeloni's Intelligent Search format
uses `AvailableQuantity` when `IsAvailable` is absent. Both retain unavailable
displayed offers, promotions and payment alternatives. Equivalent repeated package
sizes agree; disagreements between SKU fields stay null with a collection issue.
Explicit protein amounts are excluded from net contents; a single name listing
different package sizes retains its price with unknown package contents and a warning.
Angeloni and Festval also support advertised kilogram prices in their verified
Curitiba API contexts. Independent storefront checks establish the price unit;
the comparison may use another Curitiba pickup location. API availability and
location fields always come from the configured regional response, without
copying a storefront's pickup selection or assuming identical branch inventory.

### Branch and delivery context

On 2026-10-29, the retailer's public
[store-selector script](https://www.supermuffato.com.br/_v/public/assets/v1/published/muffatosupermercados.store-theme@0.0.190/public/react/SelectorSalesChannel.min.js)
mapped `sale_channel:8` to **Curitiba - Champagnat**. Its selection uses the `sc`
URL parameter. The default channel `1` maps to Campo Mourão. Every collection
request explicitly includes `sc=8`; the configuration must retain this mapping
when attaching Curitiba context.

`context.store_id` is `sales-channel:8`, explicitly identifying the storefront
branch selection, not an internal warehouse ID. City/state are Curitiba/PR;
seller ID is `1`. This is an **online branch catalog**: no delivery CEP has been
selected or verified, so `postal_code` remains null and `channel` is `online`.
It does not establish delivery coverage or the final checkout price for an address.

The source follows the [VTEX Search API](https://developers.vtex.com/docs/api-reference/search-api):

```text
GET /api/catalog_system/pub/products/search?fq=skuId:25978&sc=8&_from=0&_to=49
```

HTTP 206 is a normal paginated response. Diagnostic/live checks can fetch an exact
SKU as above; normal collection uses `ft=<target search query>` with `_from`/`_to`
pagination. It examines every returned SKU and selects the configured seller.

### Parsing boundaries

Fetching, pure parsing, contract models, batching, and delivery are separate modules.
JSON prices are decoded as Decimal, never float, then serialized as exact two-place
money strings. All three adapters retain individually sold packaged goods
(`measurementUnit=un`, `unitMultiplier=1`). The SKU-aware contents resolver uses
unambiguous measurements in the selected SKU's `name` and `nameComplete`, including
nonterminal sizes and equivalent repeated measurements. Units are `g`, `kg`, `ml`
and `l`, with spaces, case differences and decimal commas supported. Conflicting
or invalid quantities produce null contents and an issue while valid prices survive.
Unknown sizes stay null on each fresh observation and appear in the run's
`unknown_packages` count. Parent/sibling metadata and prior sizes never fill gaps.

Muffato's verified sales channel `8`, seller `1`, without a delivery CEP also
supports advertised kilogram prices with positive multipliers up to twenty. Captured
produce, beef and bakery listings were checked against the rendered Champagnat
storefront. `Price` and `ListPrice` are kilogram amounts; the multiplier is never
applied to them. Package is null even when a name contains `1kg` or an approximate
portion weight. The latter wording is preserved in offer conditions. Short numeric
retailer codes on these loose products become null GTINs; malformed full-length
GTINs are reported and omitted while otherwise valid observations survive.
Kits, other units, invalid multipliers and unverified
shop/context mappings remain explicit issues.
The larger bound includes the source's 14 kg whole-watermelon portion and 1.5 kg
beef portion; it does not multiply or divide their advertised kilogram amounts.

Angeloni enables this mapping on channel `1` with regional seller
`superangeloni24`; Festval on channel `2` with `meufestvaldark` and the
`curitiba` marketing segment. Both require a freshly resolved region, seller `1`,
and configured Curitiba/PR context. Captured fractional multipliers and rendered
`/ KG` or `/kg` labels establish the advertised basis independently of portion
totals. Angeloni's sampled offers have no payment alternatives. Festval's portion
totals remain omitted under the same explicit diagnostic rule as Muffato's.
Festval's Carlos de Carvalho pickup is in Bigorrilho, Curitiba; exact pickup
equality is not required by the city-wide scope. Angeloni's storefront branch
was not independently identified; collection location remains established by
the verified Bigorrilho API region. Storefront availability does not overwrite it.
See [regional source evidence](tests/fixtures/stores/README.md).

Weighted `PaymentOptions` totals describe portions and have no verified per-kg
mapping. They are omitted with a `payment-basis` diagnostic: independently valid
base prices are delivered, but the run reports incomplete collection. No conversion
from estimated totals, guessed promotional minimum or final checkout total is made.
Missing prices and explained unavailable placeholders still produce empty offers.
The storefront warns that final weighed totals can vary.

Muffato's verified egg-carton names ending in `12un` (or another explicit count)
map to quantity in `unit`, count 1. Homogeneous multipacks, mixed kits, bonus
bundles and structured-only sizes remain deferred; sampled responses contained no
verified complete SKU-specific structured net-content fields. No extra per-product
request was added. See the [source mapping and provenance](tests/fixtures/README.md)
for supported rules and remaining unknown-size coverage. Reliable size history is
an input to later shrinkflation analysis; no detector or replacement matching is added.

Availability and displayed prices are independent. Missing prices stay unknown;
unavailable zero-price placeholders produce an empty offers array. Promotion
structures and payment alternatives are retained, including full installment
totals. Identical payment terms across card brands share an offer with the brands
listed in its description. Membership, coupon, and minimum-quantity requirements
remain null when the source does not establish them; promotion wording stays in
the description. Offers exceeding contract limits fail validation rather than
being silently truncated.

## Delivery to the core

Configure the running core with matching `INGESTION_SCRAPER_ID` and
`INGESTION_SHOP_IDS=super-muffato,angeloni,festval`. An administrator must register the shops before
the worker processes observations; the scraper itself never accesses PostgreSQL:

```sql
INSERT INTO shops (id, name, website_url)
VALUES ('super-muffato', 'Super Muffato', 'https://www.supermuffato.com.br'),
       ('angeloni', 'Angeloni', 'https://super.angeloni.com.br'),
       ('festval', 'Festval', 'https://www.festval.com')
ON CONFLICT (id) DO NOTHING;
```

Use the existing core setup instructions in [core/README.md](../core/README.md).
With the matching token exported under the configured `ingestion_token_env`, `collect` sends newly
collected prices automatically. To retry batches saved after delivery failures, run:

```sh
.venv/bin/inflacao-scraper --config config.toml deliver
```

Delivery reuses the exact attempted UTF-8 body during retries and, for failed
batches, after restarts. Batches are limited to 100 observations and 1 MiB,
including their envelope. Each local
SQLite spool uses synchronous transactions and defaults to **64 MiB of pending
payload bytes**; database metadata/journaling needs additional disk space. A full
spool stops collection explicitly without deleting queued batches.

An empty 202 or 200 response acknowledges delivery. New successful batches are
never stored locally; retrying a saved batch removes it only after acknowledgement.
Network/transient failures use bounded retries. Exhausted retries, authentication,
validation, redirects, and unexpected response bodies save a new batch locally
and stop collection for investigation. An unsuccessful `deliver` leaves existing
batches queued. Identity mismatches also stop delivery. Tokens and response bodies
are not logged.
Check the core's diagnostics for `processed`: acceptance confirms queueing only.
Core integration tests separately exercise the shared kilogram example through
authenticated acceptance, worker processing, history persistence and retry
deduplication using disposable PostgreSQL Testcontainers. They also verify fixed
size/component reductions and later unknown sizes. This does not verify delivery
to a running deployment or the historical queued live measurements below.

### Pending end-to-end verification

Two fixed-scope Muffato runs collected 48 observations on 2026-10-29 with fresh
IDs and timestamps. Those observations were queued locally; their delivery and
persisted history have not been verified. These runs predate core-owned target
discovery and automatic delivery.

After registering the shops and configuring authorization, deliver any pending
batches and verify two collection runs against the same scope:

- Accepted submissions reach `processed`; investigate retries and failures through
  core diagnostics.
- Persisted prices, packages, conditions and store context match the observations.
- Fresh measurements retain distinct IDs and timestamps while compatible products
  and listings reuse their catalog records.
- Retrying an interrupted submission preserves its payload and identities without
  duplicating history.

Inspect PostgreSQL manually for this operational check. Automated persistence
tests belong to the core and must use disposable Testcontainers with automatic
cleanup. Scrapers continue to use HTTP only.

Further work includes additional verified shop contexts, structured net contents
and multipacks, a core history API and web view,
automated raw-payload retention, and collection-coverage reporting.
Aggregate metrics require documented baskets, weighting, comparison periods and
missing-data treatment before inflation or official-index comparisons.

## Tests

```sh
# Offline fixtures, ingestion-contract compatibility, and mocked delivery behavior.
.venv/bin/pytest
.venv/bin/ruff check src tests
.venv/bin/ruff format --check src tests

# Real API requests across all three stores.
.venv/bin/pytest -m live --live
# Only the new adapters: regional prices and Angeloni pagination.
.venv/bin/pytest tests/stores/test_live.py -m live --live
# Bounded fresh produce, beef and bakery checks for the verified Muffato mapping.
.venv/bin/pytest tests/weight/test_live.py --live
# Six regional produce/beef/bakery checks, preserving each shop's collection route.
.venv/bin/pytest tests/stores/test_live.py -k advertised_kilogram --live
```

No PostgreSQL, Docker, or live shop is required by the default suite. Delivery
tests use HTTPX MockTransport and temporary local queue files.

The opt-in live tests make actual requests, validate the retailer's response
against `tests/fixtures/muffato-response-schema.json`, and run the parser. Removing
a required field or changing its type fails the tests. Additive fields are
allowed; changing prices, inventory, and promotion text are not snapshot failures.
An unavailable/blocked API or a missing selected SKU also fails, rather than
silently skipping. Run this command periodically to detect upstream changes;
no automated schedule or notification has been installed.

The saved fixture is a small projection of a real response; see
[fixtures/README.md](tests/fixtures/README.md) and
[regional-store fixtures](tests/fixtures/stores/README.md). The ingestion schema is packaged
so installed collectors work outside a source checkout. Its equality with the
core-owned shared schema and all three shared examples is tested. After a coordinated
contract change, refresh it from the repository root:

```sh
cp docs/contracts/ingestion/v1/schema.json scrapers/src/inflacao_scrapers/ingestion_v1.json
```

### Search URL encoding

Shared VTEX target searches encode spaces as `%20` rather than `+`. On
2026-10-30, requests from the VPS for `batata doce` and `creme dental` returned
HTTP 400 with form-encoded spaces and HTTP 200 with percent-encoded spaces.
The change preserves query text, accented characters, literal plus signs, pagination,
SKU filters and regional parameters; it applies to Muffato and Festval searches.
Angeloni continues using its category-based collection route.

### Invalid product metadata

Product links are URI-encoded before submission, preserving existing percent escapes.
Invalid source barcodes are reported as `barcode:` diagnostics and submitted as unknown
GTINs, preserving otherwise valid observations and retailer SKU identities. No digits
are added, corrected, or inferred; valid barcodes retain their original representation.
Known short retailer codes for verified kilogram listings remain unknown GTINs.

### Nutrition quantities and ambiguous listings

Explicit protein claims such as `20g de proteína` and `12g Protein` are excluded
from net-content measurements. Remaining measurements must agree; the final weight
is not selected blindly. A SKU name listing multiple different sizes (such as the
104g/109g Pringles collector listing) retains its observation with unknown package
contents and an explicit warning; no size is guessed.
Disagreement between otherwise unambiguous SKU name fields still preserves the price
with unknown package contents.

The verified Angeloni Curitiba kilogram context accepts positive unit multipliers
up to 5, covering whole watermelon. Advertised kilogram prices are never scaled by
the multiplier; estimated item/payment totals remain excluded. Larger multipliers,
such as 200 on the ham listing, remain unsupported. Muffato retains its original bound; Festval's expanded bound is documented below.

### Festval weights and Mentos product-line labels

The verified Festval Curitiba kilogram context accepts positive multipliers up to
10, covering the observed 1.1kg, 1.8kg, 2kg, 6kg and 10kg listings. Prices remain
per kilogram; whole-item payment totals are excluded. Larger values and unverified
regional contexts remain unsupported. Angeloni's verified bound remains 5; Muffato's
remains 1.

The verified `Mentos 3L` product-line label is excluded from package measurements.
Its separately stated 8.5g remains the package size; unrelated `3L` quantities
remain liters. Genuine conflicting SKU sizes remain unknown while independently
valid prices are retained.


### Collection errors and metadata warnings

`ParsedPage.issues` identifies skipped observations or incomplete collection.
`ParsedPage.warnings` reports omitted optional metadata or payment alternatives
when the observation's independently valid base offer can still be retained.
Barcode, reference-price, package-size and optional payment diagnostics remain
visible on stderr; run summaries report `warnings` separately from `failures`.
Warnings alone do not make collection or discovery exit with a failure status.
Missing targets, invalid base prices, unsupported sale formats, source/network
errors, pagination failures and failed delivery still fail completeness.

Sonda and Pão de Açúcar attempt independent departments after a source or
pagination failure. Errors include the department and failing page; the final
run remains incomplete even when later departments succeed. Overlapping products
on advancing pages produce warnings and the shared runner retains one measurement
per listing. Duplicate identities within a page, pages with no new identities,
changed totals and malformed pagination remain failures. Delivery failure still
stops collection immediately and preserves the failed batch in its spool.

Run summaries separate total `observations` from `available_price_observations`
and `unavailable_observations`. Matching a monitoring target does not mean a
currently available price was found; unavailable products remain unavailable.

The shared parser normalizes measurement-unit spelling and whitespace (`UN`,
`un`, ` Un `). On 2026-10-31 the VPS returned `measurementUnit=UN` and multiplier
1 for Muffato SKUs 306771 (Fini 35g) and 301876 (Adidas 150ml). These retain
package prices; multiplier bounds and regional kilogram policies still apply.
Ambiguous package quantities remain unknown and are excluded by core package
comparability rules rather than being guessed or discarding the observation.

### Verify the deployed browser runtime

From the repository root, build a verification image and run the disposable
Testcontainers browser smoke (using a Python environment with pytest and
Testcontainers installed):

```sh
docker build -f deployment/scrapers.Dockerfile -t nossa-inflacao-scrapers:verify .
python -m pytest deployment/tests/test_scraper_browser.py -q
NOSSA_LIVE_SHOPS=1 python -m pytest deployment/tests/test_scraper_browser.py -q
```

The default check opens a local HTML document. The explicit live check performs
Hirota discovery in that same container, without contacting the core or ingesting
observations. Containers register cleanup before startup, including failed tests.
The image runs Chromium as the collector user with its own writable home directory.

## Pão de Açúcar

The [standalone configuration](pao-de-acucar.example.toml) uses ordinary HTTP,
with no browser extra. Resolve Ricardo Jafet store 461 / ENTREGA EXPRESS 842 for
public-address CEP 04115090 every run. This differs from Mambo's MASP context.
Category browsing is bounded to 2,000 pages of 12 products, filtered by the core
scope. Unknown club/payment/coupon restrictions stay unknown. Advertised quantity
and nth-unit averages retain their package thresholds; kg promotions inherit their
parent rule's restrictions. Item-count thresholds never become kg thresholds.
Without an advertised kg price, identity and availability survive with no offer and
an explicit warning. Invalid reference metadata is omitted without rounding it or
discarding an independently valid selling price. Unsupported restrictions still
produce issues. See the
[source evidence and supported formats](../docs/evidence/pao-de-acucar-onboarding.md).

From `scrapers/`:

```sh
.venv/bin/inflacao-scraper --config pao-de-acucar.example.toml discover --query arroz --limit 1
.venv/bin/pytest tests/pao_de_acucar/test_live.py --live -q
```

Use `collect` with an authorized core token and monitoring API to ingest. The
combined SP example leaves this entry disabled until deployment is ready. Full
scope coverage and two dates of live history have not been measured.

### Additional capital contexts

The active local configuration and `scrapers.example.toml` enable these additional
contexts with the existing collector identity and a separate spool per entry:

| Retailer | Capital | UF | Branch |
| --- | --- | --- | --- |
| Pão de Açúcar | Rio de Janeiro | RJ | 1850 / Paróquia |
| Pão de Açúcar | Brasília | DF | 1870 / W3 |
| Pão de Açúcar | Goiânia | GO | 1569 / Flamboyant |
| Pão de Açúcar | Fortaleza | CE | 521 / São João |
| Pão de Açúcar | Recife | PE | 1649 / Parnamirim |
| Pão de Açúcar | João Pessoa | PB | 1807 / Bessa |
| Pão de Açúcar | Natal | RN | 2232 / Natal Midway |
| Pão de Açúcar | Aracaju | SE | 1204 / Jardins |
| Pão de Açúcar | Teresina | PI | 1101 / São Cristovão |
| Pão de Açúcar | Campo Grande | MS | 1203 / Caranda Bosque |
| Angeloni | Florianópolis | SC | superangeloni14 / Beira Mar |

Pão de Açúcar resolves the configured delivery CEP every run, requires the expected
store and delivery modality, and independently verifies branch name, city, postal
code and address number. Branch and delivery postal codes may differ. The settings
retain Ricardo Jafet defaults for existing configurations. Offer conditions preserve
`customerPlus=true` with membership, payment and coupon eligibility unknown; the
observation context carries the actual branch, city and UF.

Angeloni resolves CEP `88015200` to Beira Mar every run. Packaged and advertised
kilogram prices are supported in this verified Florianópolis context. Rendered
Beira Mar fruit, meat and bread prices established the kilogram basis; portion
multipliers never become fixed package contents. Other unverified locations retain
their existing restrictions.

New entries use stable `schedule_id` values to distinguish scheduled contexts of
the same retailer during deployment upgrades. Preserve these identifiers when
customizing local addresses. `git pull` followed by `./deploy up` appends missing
contexts before recreating the scheduler, preserving original entries and explicit
disables. Collector identity, core URL and token environment-variable name are
inherited from the existing configuration. Shop registration and authorization
already include both retailer IDs. Configuration does not prove a running scheduler.

Read-only live diagnostics from `scrapers/`:

```sh
.venv/bin/pytest tests/pao_de_acucar/test_live.py --live -k capital -q
.venv/bin/pytest tests/stores/test_florianopolis.py --live -q
```

Live samples and storefront comparisons cover these branches, not every monitored
product or complete catalog runs. No collection is configured for the researched
noncapital cities. See [captured fixture evidence](tests/fixtures/stores/README.md).

### Sonda

The public HTML adapter needs the normal HTTP dependencies, with no browser or
login. Use [sonda.example.toml](sonda.example.toml) for discovery and collection.
The source is the public online catalog: branch, city, CEP and pickup prices
are unverified and stay unknown in ingestion. All 14 main-menu departments are
discovered, including departments absent from the featured menu. Public-catalog
provenance is reported once per run. A changing page count restarts that department
once, sharing the original page budget; repeated instability remains an error.
The default budget is 1,200 pages across all departments.

Fresh and deli listings with a declared portion preserve their advertised
whole-item/portion amount with package basis and unknown fixed contents. Ambiguous
weight bases retain identity with no offer and a warning. They never become inferred kg prices.
Quantity badges with an advertised average preserve their group threshold;
second-unit-only prices stay in the description instead of becoming a uniform
unit price. Unknown badge formats remain errors. See
[source evidence, commands and rollout limits](../docs/plans/sonda-retailer.md).


The default local `config.toml` and versioned `scrapers.example.toml` include all
ready adapters. New production installations copy that template. For existing installations, `./deploy up` appends missing adapters to
`/etc/nossa-inflacao/scrapers.toml` after building and stopping the old scheduler,
then recreates it. Existing entries, including explicit disables, are preserved. Retain the collector identity authorized by that core,
separate spool paths, and the matching shop authorization/registration.

### History refresh after collection

After each collection run (including a partial run with committed observations)
and after spool delivery, the shared runner requests asynchronous history refresh
through `POST /api/v1/ingestion/history-refresh`. It uses the same authorized
collector/shop identity and private core URL as ingestion. The core waits for its
pending ingestion queue to drain before recalculating saved selections. This does
not assert that every shop completed successfully. Notification errors are reported
as warnings; collection status and durable batches are preserved. The core's
periodic revision check recovers a missed signal. Deploy the updated core before
updating independently hosted collectors to avoid refresh-endpoint warnings.

## Atacadão capital branches

The `atacadao` adapter uses ordinary HTTP and the public storefront's FastStore
`ProductsQuery`. Each run independently verifies the configured seller in the
public store directory, checks its branch page's ID, slug, name, city, UF and
current postal code, and probes the catalog for the same seller. Every price
request specifies that seller and sales channel `1`. Block pages, empty branch
catalogs, seller mismatches, aged responses and pagination drift fail visibly.
An individual failed city does not stop other configured entries.

The default schedule and active local configuration add 22 enabled contexts:
Rio Branco, Maceió, Manaus, Salvador, Fortaleza, Brasília, Goiânia, São Luís,
Belo Horizonte, Campo Grande, Cuiabá, Belém, Recife, Teresina, Curitiba,
Rio de Janeiro, Natal, Porto Alegre, Florianópolis, Aracaju, São Paulo and Palmas.
They retain the existing collector identity and use distinct `atacadao-<uf>`
schedule IDs and spool paths. No browser dependency is required.

All 27 capitals were checked on 3 November 2026. Five are not scheduled because
of concrete source blockers: Macapá's two listed catalogs and Boa Vista's listed
catalog were empty; Vitória had no online seller mapping; João Pessoa's branch
page disagreed with the directory about its seller; Porto Velho's seller mapping
was absent from the online directory and its sampled seller returned no products.
These restrictions are collection findings, not claims that the physical shops
are closed or that every delivery address is unsupported. Add a context when its
branch identity and priced catalog can be independently verified.

Observations use `channel=online` and null delivery CEP. `branch_postal_code`
validates the store address; it does not represent a selected delivery address.
Retail and quantity-discount prices remain separate offers, with the minimum
purchase expressed in the offer's basis. `unitPerBox` does not change the package
size. Advertised kg prices stay per kg; `unitMultiplier` describes an approximate
purchase portion, never fixed package contents or a multiplier for the price.
Payment, membership, coupon and missing availability remain explicitly unknown.
Search omits stock, so a separate anonymous, read-only storefront simulation
checks the requested SKUs and seller in one batch per matching page. Its stock
statuses are retained without replacing catalog prices with simulated cart totals;
this provides confirmed stock for the core's price views. No cart or order is created.
The GraphQL `gtin` field contains internal article references in verified samples;
it is not emitted as a barcode. The core derives comparable units as usual.

From `scrapers/`, read-only discovery and opt-in live checks are:

```sh
.venv/bin/inflacao-scraper --config atacadao.example.toml discover --query arroz --limit 3
.venv/bin/pytest tests/atacadao/test_live.py --live -q
```

The standalone example selects Vila Maria, São Paulo. The combined schedule has
all ready contexts. Source fixtures cover every enabled capital, quantity bands
and approximate-weight products. Full scope coverage, accumulated daily history
and production execution must be measured separately from these source checks.


## Carrefour delivery collection

`carrefour` supports 13 independently verified grocery delivery-region catalogs:

| Schedule | City | CEP | VTEX region |
| --- | --- | --- | --- |
| `carrefour-sp` | São Paulo/SP | `01310100` | `v2.4FC957AB8941A10397B85207B23C2F55` |
| `carrefour-rj` | Rio de Janeiro/RJ | `22041001` | `v2.7270B316E593B206E6E0275E7718FBF4` |
| `carrefour-am` | Manaus/AM | `69005040` | `v2.BF533D0AEECE42C36BD9B8DA285BEF38` |
| `carrefour-df` | Brasília/DF | `70390025` | `v2.3AAC323080B05FB702A3AB2ABAA90E3B` |
| `carrefour-es` | Vitória/ES | `29010001` | `v2.7D0ED687024A66050E0FD3832B8BD6AA` |
| `carrefour-go` | Goiânia/GO | `74810100` | `v2.F05A3DA1C76D4CCCAFB4EBFB21F46381` |
| `carrefour-mg` | Belo Horizonte/MG | `30130010` | `v2.0E68B2A9BF71F2194EF2890250AAAAF4` |
| `carrefour-ms` | Campo Grande/MS | `79032040` | `v2.11FA59941738A4965184405D490939EC` |
| `carrefour-pb` | João Pessoa/PB | `58039000` | `v2.80E9F1AA89E1A658455D7B622AA088BF` |
| `carrefour-pe` | Recife/PE | `51021000` | `v2.B8D4DEE82CCFA7FBA645F5E26E2A24C2` |
| `carrefour-pr` | Curitiba/PR | `80730201` | `v2.DBEC9A35D9DE71C4BB85CA48A5354448` |
| `carrefour-rn` | Natal/RN | `59020100` | `v2.D9CE56FB0EB73802601410FB432111F4` |
| `carrefour-sc` | Florianópolis/SC | `88015200` | `v2.053EF8325AA06E6F886118F67CAFA4AB` |

All are enabled in the default and active local schedules, retain the existing
collector identity and use separate spools. `carrefour.example.toml` contains
all scheduled entries. Other CEPs or region mappings are rejected until independently
verified. These are delivery-region observations, not physical-branch prices
or proof of delivery coverage throughout a city. Seller `1` / Carrefour
is shared; `store_id` preserves `region:<id>/seller:1` rather than inventing a
physical branch. Vitória's context is an actual delivery CEP in Vitória. The
pickup directory's Vila Velha entry is not counted as a Vitória branch.

The other 13 capitals are not scheduled: Rio Branco/AC, Maceió/AL, Macapá/AP,
Salvador/BA, Fortaleza/CE, São Luís/MA, Cuiabá/MT, Belém/PA, Teresina/PI,
Porto Velho/RO, Boa Vista/RR, Aracaju/SE and Palmas/TO. Their sampled CEPs returned
Carrefour's explicit no-serving-store response, and no matching capital was
listed in the grocery pickup selector. This records the tested online contexts;
it does not assert that all addresses or other sales channels are unavailable.



Porto Alegre/RS is also not scheduled. Its CEP and regional catalog resolve, but
repeated live checks returned inconsistent totals for successive rice pages
(for example, 54 then 55), including a second sampled neighborhood. The parser
preserves its unavailable-product shape, and its verified geographic mapping is
retained for diagnostics. Scheduling must wait for a complete consistent source
traversal; the adapter's catalog-integrity checks are not relaxed for this city.

Install the browser extra described above and run, from `scrapers/`:

```sh
.venv/bin/inflacao-scraper --config carrefour.example.toml discover --query arroz --limit 3
.venv/bin/pytest tests/carrefour/test_live.py --live -q
```

The discovery command checks all configured cities. Live tests accept
`CARREFOUR_CHROME_PATH` when browser autodetection is unsuitable; scheduled
entries accept `chrome_executable_path`. Chromium and the browser dependency
are already included in the deployment image.

Each city gets a fresh anonymous Botasaurus driver for its entire run, closed
on success, selection failure or failed delivery. It selects the CEP through
the normal grocery storefront and verifies the server's returned CEP, region,
city and residential-delivery status. The effective browser context is checked
before and after every search response. No customer account, saved profile,
proxy or CAPTCHA solver is used. Browser tasks do not cache/export results or
retry implicitly. Requests are paced, carry fresh request IDs and bypass caches;
aged, redirected, challenged and malformed responses fail visibly.

Prices come from the grocery storefront's `/busca/<query>.data` loader, not the
blocked general shopping host or legacy VTEX endpoints. Original response text
is decoded in Python with exact decimals; JavaScript does not parse monetary
JSON. Only the observed reference-table subset is accepted. Search totals,
page indices, page sizes and product identities are checked, with per-query
and per-run request budgets. Core name rules filter unrelated search hits, and
the shared pipeline handles deduplication, batching and durable delivery.

Regular prices, bulk thresholds and distinct supplied payment prices remain
separate offers. Missing EAN stays null. Stock comes from explicit source
availability quantity; a missing/zero unavailable price produces no offers.
When `bestSeller` is explicitly null, a single Carrefour offer can only be
retained if its stock quantity explicitly says zero. A missing seller ID remains
null; available or ambiguous sellers never become a fallback.
For `kg` items, the verified `Price`/`ListPrice` are per kg; calculated prices
and payment totals can describe approximate portions and never replace them.
No fixed package is inferred from those portions. Weighted bulk offers have no
verified minimum/basis mapping and are rejected with an explicit collection
issue. Fixed-package contents use conservative name extraction, including the
observed rice grade delimiter in `Tipo 1 - 5kg`; display names remain unchanged.

The adapter was smoke-tested from the existing EU VPS for every enabled capital,
checking regional selection, two rice-query pages and banana offers. The initial
São Paulo/Rio checks also traversed their entire rice result sets. This verifies
bounded live extraction; it does not establish daily reliability, complete
96-target coverage or delivery-slot availability. Actual shop registration and
ingestion authorization follow [deployment setup](../docs/deployment.md).

## GBarbosa delivery collection

The `gbarbosa` adapter collects the retailer's own public VTEX catalog over HTTP;
it needs no browser, new dependency or marketplace. Three delivery contexts are
enabled in the default schedule:

| Schedule | City | Delivery CEP | Required regional grocery seller |
| --- | --- | --- | --- |
| `gbarbosa-se` | Aracaju/SE | `49026010` | `gbarbosab006` |
| `gbarbosa-ba` | Salvador/BA | `41820020` | `gbarbosab035` |
| `gbarbosa-al` | Maceió/AL | `57035000` | `gbarbosab084` |

Every run resolves its CEP again and requires the expected local seller before
fetching prices. Search requests include the resolved region and public VTEX
segment cookie. Observations retain SKU, product URL, offer seller `1`, regional
seller/region in the store identity, CEP, city/state and delivery channel. These
are online delivery catalogs, not verified physical shelf prices or delivery to
every address in a city. The sampled Fortaleza CEP `60150160` resolved only the
shared `gbarbosab101` seller and returned unavailable grocery samples; Fortaleza
is not enabled. This is a sampled-address blocker, not proof of citywide absence.

Collection uses bounded, paced target searches from the core's monitoring scope,
with explicit source pagination, repeated-page detection and incomplete-run
reporting. New target names and brands do not require adapter changes. Missing
coverage, unsupported formats, access failures and exhausted page limits remain
visible. Shared batching, immutable retries and per-context spools own delivery.

Packaged prices and advertised kilogram prices are supported. Source kg prices
stay per kg; approximate portions up to the captured 1.7 kg limit do not multiply
prices or become fixed package contents. Payment-option portion totals are
omitted for kg offers with a warning. Unsupported larger portions and kits remain
explicit issues. Fixed package contents use conservative name parsing. Zero
unavailable placeholders produce no offers; unknown membership, coupon and
quantity conditions remain null. Available promotion wording and separate payment
offers are preserved, without inventing a qualifying threshold.

From `scrapers/`, a diagnostic sample performs no ingestion or spool writes:

```sh
.venv/bin/inflacao-scraper --config gbarbosa.example.toml discover --query 'arroz branco' --limit 3
.venv/bin/pytest tests/gbarbosa/test_live.py --live -q
```

The three enabled entries use the existing authorized collector identity and
distinct `data/gbarbosa-<uf>/spool.sqlite3` queues. Existing VPS upgrades append
missing entries and register/authorize the shop through `git pull` followed by
`./deploy up`; custom settings and explicit disables survive. See
[deployment guidance](../docs/deployment.md#gbarbosa-delivery-collection).

Saved [API fixtures and independent storefront checks](tests/fixtures/stores/README.md)
cover three capital contexts. Read-only smoke checks also verified extraction
through the existing VPS runtime. This does not establish full 96-target coverage,
ongoing scheduler health or price history on two separate dates. The development
workspace's enabled configuration is distinct from a deployed production scheduler.
