# Unofficial web API with email and password login

Bilka offers no customer API (the Salling Group developer portal only exposes stores, jobs and offers), so we call the same backend the bilkatogo.dk web app uses: Gigya `accounts.login` → `accounts.getJWT` (24 h) → `POST api.bilkatogo.dk/api/auth/LoginJWT`, then `v7/OrderHistory` and `v7/OrderDetails`. We store the customer's email and password and log in again on our own, instead of having them paste the login token from the browser, because a pasted token expires and would break status tracking without the customer noticing.

## Consequences

- The API is undocumented and can change without notice; parsing must tolerate unknown fields and status codes.
- Automated access may conflict with Bilka's terms; the user accepted this risk.
- Polling is kept adaptive and low-frequency so the traffic looks like a person checking their order.
