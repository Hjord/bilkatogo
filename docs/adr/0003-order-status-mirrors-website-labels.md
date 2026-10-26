# Order Status mirrors the website's labels, not Bilka's status codes

Bilka's backend returns Danish codes such as `Bestilt`, `Leveret` and `Faktureret`, but the website shows the customer different words: `Bestilt` is shown as "Modtaget", and `Leveret` and `Faktureret` both as "Afhentet og faktureret". We expose the website's states (copied from Bilka's own `MyAccountOrderStatus` mapping), because those are the words customers know and automate against. The raw Bilka Status Code is kept next to it for debugging.

Once Home Assistant users build automations on these states, renaming or splitting them is a breaking change. That is why this decision is recorded.
