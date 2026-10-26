# Product search through the website's Algolia index

The bilkatogo.dk website searches Products directly in Algolia (application `F9VBJLR1BK`, index `prod_BILKATOGO_PRODUCTS`) with a public search-only key. We use the same index rather than Salling Group's official developer API. The official API needs its own key and describes the physical Bilka stores, not the online shop's Prices, Offers and stock. The Algolia index has those per Store (`storeData`, keyed by the Store id that `shop/v6/AvailableDeliveryAddresses` returns for each Pickup Point).

The application id and search key are hardcoded like `GIGYA_API_KEY` instead of being scraped from the website on every run. Scraping would add a fragile HTML dependency to every search to protect against a rotation that has not happened yet.

## Consequences

- If Bilka rotates the key or renames the index, search breaks until a new release ships the new values.
- The same unofficial-access caveats as ADR 0002 apply, and Algolia is a second third party whose terms we depend on.
