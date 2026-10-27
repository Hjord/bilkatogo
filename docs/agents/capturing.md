# Capturing Bilka responses

A capture is a real Bilka response saved as a fixture in `tests/fixtures/`, replacing a guessed shape. Every committed capture is redacted.

## Picking the route

1. **Read-only calls (`Cart`, `OrderHistory`, `OrderDetails`)**: use the library's own session with `bilkatogo order <number> --raw --redact` and `bilkatogo cart --raw --redact`. Check the output for anything personal the redaction missed before committing it (a home delivery address is detected by guess). The Cart belongs to the account, so the library reads the same Cart the website shows.
2. **Anything the customer does on the website (Cart changes, warnings, rejections)**: the maintainer acts in the Chrome DevTools MCP browser while logged in; the agent reads the network log afterwards. The agent never types the password and only sends writes the maintainer has confirmed.

## Reading the browser's network log

- List with `list_network_requests` filtered to `resourceTypes: ["xhr", "fetch"]` and a `pageSize` of 20 or less, paging from the end; the unfiltered log runs to 90k characters of analytics.
- Fetch bodies with `get_network_request` and a `responseFilePath` outside the repo, then inspect the saved file with a script. The tool prints the request headers inline, including `jwt_token` and cookies, so fetch only the requests you need and ask the maintainer to log out of the browser when done.

## Redaction

Replace before committing: name, email, address, phone, Pickup Code, real Order Numbers (use `9000000000xx`), and the customer ids `uid` (use `900001`) and `tid` (use `00000000-0000-0000-0000-000000000000`). Pickup Points and Stores are public and stay. Grep the result for the maintainer's name and email before committing.

## Finding a Product with a limit per customer

Query Algolia (constants in `src/bilkatogo/const.py`) with `isInAssortmentIn:<sid> AND nonsearchable:false` and check `storeData[<sid>].offerMax > 0`. Algolia returns at most 1,000 hits per query, so an empty result over the whole assortment is not proof; split the query by category or text.
