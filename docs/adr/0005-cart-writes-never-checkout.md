# Cart writes, never checkout

From v3 the client changes the customer's Cart: it sets the quantity of a Product by Article Number (`shop/v6/ChangeLineCount`, 0 removes the Cart Line) and empties the Cart (`shop/v6/EmptyCart`). These are the first writes against Bilka's private API. We stop at the Cart: the client never chooses a Pickup Slot or Pickup Point, places, pays for or cancels an Order. A Cart change is reversible and costs nothing; a placed Order spends the customer's money and commits Bilka to packing it, so a bug or a misread response there has real consequences that a test against a fake backend cannot rule out.

Bilka enforces its own rules on a Cart change (stock, assortment, Offer limit per customer) and the client does not check them in advance. In every capture a change answered HTTP 200 with `eid: -1`; Bilka's Danish `message` or `offerLimitMessage` can accompany a change it applied (99 cucumbers: "Ring venligst til kundeservice ..."), so a message is a warning, not a failure. The client treats a change as rejected only when Bilka applied a different quantity than asked (`productAmount` differs from `count`), and raises that with Bilka's message.

## Consequences

- Anything past the Cart, including choosing the Pickup Point, needs a new decision that supersedes this one.
- The CLI changes the Cart without a confirmation prompt, but offers no command to empty it, so one mistyped command cannot throw away a Cart the customer built up.
- Every write is checked by hand once against the maintainer's own Cart before a release; CI only exercises the fake backend.
