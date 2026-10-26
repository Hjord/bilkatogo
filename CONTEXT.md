# BilkaToGo

Tracking a customer's BilkaToGo grocery orders (Salling Group's online shop at bilkatogo.dk) from the moment they are placed until they are collected, including which products Bilka swapped for something else.

## Language

### Orders

**Order**:
One purchase placed in BilkaToGo, identified by its Order Number, collected or delivered in one Pickup Slot.
_Avoid_: Purchase, basket, cart (a Cart is the not-yet-placed order)

**Current Order**:
The unfinished Order with the earliest Pickup Slot or, when every Order is finished, the most recently finished one.
_Avoid_: Active order, latest order, open order

**Order Number**:
The 12-digit identifier Bilka shows as `#902852320314`.
_Avoid_: Order ID, reference

**Order Line**:
One ordered product with its quantity inside an Order.
_Avoid_: Item, row

**Pickup Slot**:
The date and time window in which the Order is collected, e.g. Tuesday 20/10, 12:00 to 14:00.
_Avoid_: Delivery interval, time slot, delivery date

**Pickup Point**:
The Bilka store where the Order is collected, e.g. Bilka Vejle.
_Avoid_: Pickup zone, warehouse, location

**Pickup Code**:
The 8-digit code the customer enters at check-in when collecting the Order.
_Avoid_: Check-in code, PIN

**Home Delivery**:
An Order that is brought to the customer's address instead of collected at a Pickup Point.

### Order Status

**Order Status**:
Where an Order is in its lifecycle, expressed in the same states the BilkaToGo website shows the customer.
_Avoid_: State, stage

**Bilka Status Code**:
The raw Danish status string Bilka's backend returns (e.g. `Bestilt`, `Faktureret`); several codes map to one Order Status.
_Avoid_: Raw status, API status

| Order Status | Danish (as shown on bilkatogo.dk) | Bilka Status Codes |
|---|---|---|
| **Processing** | Ubehandlet (and Bilka's generic "in progress" label) | `Ubehandlet`, `Capture igang` |
| **Received** | Modtaget | `Bestilt` |
| **Packed** | Pakket | `Pakket` |
| **Picked Up** | Afhentet og faktureret | `Leveret`, `Faktureret` |
| **Not Collected** | Uafhentet | `Uafhentet` |
| **Cancelled** | Annulleret | `Annulleret` |
| **Sold Out** | Fuldt udsolgt | `Fuldt udsolgt` |
| **Unknown** | Ukendt | any other code |

Note that Bilka says "Modtaget" (received) for the code `Bestilt` (ordered); the Order Status follows what the customer sees, not the code.

### Substitutions

**Substitution**:
An Order Line Bilka could not fulfil and replaced with a different product, shown on the website as "erstattet". It pairs the Original Product with its Replacement Product.
_Avoid_: Replacement (on its own), swap, erstatningsvare (use only as the Danish alias)

**Original Product**:
The product the customer ordered on a Substituted Order Line.

**Replacement Product**:
The product Bilka packed instead of the Original Product, e.g. Kiwi instead of Blommer.
_Avoid_: Erstatningsvare in code

**Missing Item**:
An Order Line that was out of stock and not replaced, so the customer receives nothing for it. Distinct from a Substitution.
_Avoid_: Udsolgt vare, OOS line
