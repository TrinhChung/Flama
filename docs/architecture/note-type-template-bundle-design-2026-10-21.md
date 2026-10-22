# Note Type bundles with original template publications

Date: 2026-10-21; follow-up verified 2026-10-22 (Asia/Tokyo). Mode: IMPLEMENTED / LOCAL VERIFIED. Engine: MySQL 8.0.

Follow-up: the four flow defects and legacy provenance gap in the [completeness review](marketplace-bundle-completeness-review-2026-10-21.md) are now fixed and verified locally. The [local rollout rehearsal](../runbooks/MARKETPLACE_BUNDLE_LOCAL_ROLLOUT_20261021.md) publishes the four existing local bundles and their standalone templates and records the provenance-only cutover of 20 old copies. Production has not been deployed.

Implements the clarified product rules following [the ownership review](marketplace-note-type-template-ownership-review-2026-10-21.md). A Note Type combines a concrete field schema, application mappings and references to template publications. Including someone else's template does not republish their received copy or transfer authorship.

## Invariants

- A reference uses the canonical authored template ID and an immutable TemplateRelease. A received template's personal HTML/CSS edits do not become the publication in a new Note Type.
- The author can publish an owned, previously unlisted template together with a Note Type, supplying its individual description, category and free/paid price. This uses the standalone listing validation and the same transaction as the Note Type release.
- Already listed owned templates reference their published head. Received foreign templates reference their subscription's applied original release. New foreign references require an available original listing and valid author access.
- `NoteType.price_amount_minor` prices the author's own bundle: structure, configuration and owned templates. This can be below the sum of the author's standalone template prices. Foreign definitions retain their source listing price and are charged separately.
- Free templates cost zero. An existing valid source-template license waives that template's fee. The own-bundle amount stays fixed, as explicitly confirmed by the product owner.
- Repeated applications of the same source require one license and one charge. Mappings and occurrences remain distinct.
- Checkout freezes every seller, line amount and release. Fulfillment grants template licenses before receiving the Note Type, credits the original sellers and is idempotent across repeated webhook delivery.
- An individual template download from a Note Type follows its original standalone listing and license; a free structure does not waive a foreign paid-template fee.

## Storage and modeling choice

| Concern | Existing authoritative store / behavior |
|---|---|
| Editable structure and mappings | `note_types`, `field_defs`, `study_applications` |
| Original template identity and working copy | `templates.owner_user_id`, `origin`, `source_template_id` |
| Standalone offer | `template_publications` pricing/status |
| Published composition | `note_type_releases.manifest_json` with canonical template ID, template release ID, attached local ID and original author ID |
| Received composition | `note_type_installs.applied_release_id` and existing frozen received applications |
| Acquired license | Source ownership, active effective payment entitlement, or existing server-issued canonical subscription without explicit revocation/expiry |
| Purchased quote | `payment_orders`, one primary Note Type item plus template grant/charge items and immutable purchase snapshots |
| Seller revenue | `user_balance_transactions`, one credit per positive order item |

Two approaches were considered: introduce normalized bundle-component/offer tables, or reuse the current application graph with the existing immutable release manifest and order items. The latter matches the existing Note Type composition and avoids a second mutable membership store. It keeps release reads atomic and retains original FKs on the source entities. Embedded release references remain service-validated rather than enforced by per-JSON-element FKs. A separate normalized offer model would be useful for independent promotional campaigns or licenses with different scopes; those are outside this change.

No new table, column or Alembic revision is required. `PaymentOrder.items` has a deterministic ORM ordering with the Note Type first because MySQL DATETIME values can tie within one second. This changes relationship ordering, not physical schema.

## Publication and API contract

`GET /api/marketplace/note-types/<id>/publish-options` is owner-only. It returns distinct attached definitions with canonical source IDs, original authors, published release, listing state, standalone price and `requires_publication`.

The existing publish endpoints accept an additional `template_listings` array for owned templates requiring publication:

```json
{
  "publish_status": "published",
  "pricing_mode": "paid",
  "price_amount_minor": 10000,
  "template_listings": [
    {
      "template_id": "owned-unpublished-template-id",
      "description": "Vocabulary presentation",
      "primary_category": "Từ vựng",
      "pricing_mode": "paid",
      "price_amount_minor": 30000
    }
  ]
}
```

Every owned unlisted template requires an explicit price choice. Entries for foreign or already listed definitions, duplicate entries and unknown properties are rejected. Missing metadata or a failed Note Type release rolls back staged template listings too. Existing installed-NoteType republish restrictions and deck publication guards remain in place.

The new manifest retains `codec=note-type-release.v1` and records `commerce_version=note-type-bundle.v1`. Each application keeps its own mapping/order/default and references the original template release. Reusing a version label for a changed complete manifest still requires a new version.

Buyer detail includes `pricing_breakdown` with `bundle_amount_minor`, `template_amount_minor`, `total_amount_minor`, `payment_required`, `available` and per-template authors, standalone prices, actual charges and existing-rights flags. Catalog price filters and displayed prices use the amount payable by the current viewer. The publisher's own editable price remains separate from that buyer total.

## Payment transaction and access behavior

For an author's discounted bundle of 10.000đ containing two owned templates listed at 30.000đ and 20.000đ, a foreign paid template at 15.000đ and a foreign free template:

| Buyer state | Own bundle | Foreign paid template | Total |
|---|---:|---:|---:|
| No existing licenses | 10.000đ | 15.000đ | 25.000đ |
| Already licensed foreign paid template | 10.000đ | 0đ | 10.000đ |
| Author makes own bundle free; buyer lacks foreign license | 0đ | 15.000đ | 15.000đ |

Owned included templates and unowned free templates can have zero-value template grant items. These grant standalone source-template rights without attributing extra revenue. There is one positive Note Type line for the own bundle and one positive line per chargeable foreign source. A zero-price Note Type primary item remains present so result navigation continues to point to the purchased composition.

Existing server-issued subscriptions preserve licenses acquired when a template was free, or included in a valid earlier bundle. Explicit revoked, refunded, expired or future-effective entitlements do not waive payment. Immediate entitlement activation truncates microseconds before writing `effective_from`: MySQL DATETIME rounding must not put a just-purchased license fractionally in the future.

Receiving a paid bundle does not by itself authorize unpaid foreign dependencies. The receipt service checks foreign license access, including when called below the REST layer. Fulfillment processes template items first, uses the checkout release snapshots, then receives the Note Type. Receiving a bundle that includes a template authored by the buyer also works without attempting to subscribe the author to their own source.

An existing pending order is reused only if primary product, amounts, source releases and sellers still match. Before checkout or a free receipt, stale positive template charges are reconciled; successful new grants trigger reconciliation again. All orders for a buyer lock that buyer first. Fulfillment checks current rights before granting or crediting, including concurrent independent quotes under MySQL REPEATABLE READ. An obsolete payable link is canceled. A payment that wins the cancellation race, or arrives late for a replaced quote, is retained under review without duplicate grants or seller credits. Provider reconciliation/refund remains an operator responsibility; there is no automatic cross-order refund claim.

## Frontend boundaries

- Publish/detail composition moved to `pages/marketplace-note-type-publish` and `pages/marketplace-note-type-detail`, with their own hooks and API adapters using the shared HTTP client.
- Business presentation fields and validation reused by standalone template publication and inline bundle publication live in `entities/card-template`; no sibling feature import was added.
- The publish wizard shows editable unpublished owned templates, read-only original foreign references and a total for buyers without existing rights.
- Buyer detail shows the original author and price of each template, the own-bundle amount and waived template fees. Unavailable references block a new bundle installation.
- Existing palette, gradients, typography, spacing and responsive layout were retained; additional pricing sections implement the requested workflow.

## Compatibility, rollout and verification

The change is additive at the API/JSON-manifest level. No source notes, learning progress, native arrays or overlay data are migrated. Historical releases remain immutable; legacy public Note Types without complete releases still need an explicit author publication. Do not backfill a historical publication from the current draft automatically. Rollback can revert the application while retaining release/order/license history; do not delete zero-value grant items or payment snapshots.

Verification performed:

- 16 pure backend tests: publication ownership, price choices, own-only discounts, repeated sources, valid rights, receipt guards, quote replacement and payment/cancellation race handling.
- Disposable MySQL 8.0.40 probe: inline paid/free publication, canonical foreign reference with edited local copy, pricing and catalog filters, no recharge, revoked/expired/future access, direct/individual receipt guards, pending quote cancellation/repricing, exact purchased release and original seller revenue, webhook replay and atomic failure rollback. Generated schemas were dropped; configured application rows were not modified. PayOS was mocked, with live clients forbidden.
- 12 focused frontend tests cover standalone publication, inline template prices, foreign read-only references, bundle totals, per-template authors and unavailable references.
- Frontend TypeScript checks and scoped Oxlint passed. Python syntax and diff whitespace checks passed for the changed implementation.
- Desktop 1440px and mobile 390px browser checks used an isolated Chrome profile and fixture API responses. Publish/detail screenshots are under `output/playwright/note-type-bundle-*.png`; no horizontal overflow was observed at 390px. These browser fixtures do not replace the real MySQL service checks.

Production deployment, a live/sandbox PayOS payment, and a complete repository suite were not performed. Existing preview CSP meta warnings remain outside this change.
