# Complete Canonical Loyalty Fixtures

These are the complete, unmodified public Scryfall named-card API response
bodies captured before the offline native tests on 2026-10-10. No Oracle clause
or unrelated ability is removed. Response headers and exact request timestamps
were not retained, so this inventory does not claim those additional receipts.
The original bodies and source URLs are also retained in verified project storage.

| Fixture | Response SHA-256 | Canonical API Resource |
| --- | --- | --- |
| `chandra-ablaze.raw.json` | `09cab95cbbbf4fa7bc6b5465a3022c6882588b5bca142e7b81fe78f392fc2d15` | https://api.scryfall.com/cards/43da8995-77da-4ec4-94a5-5e7932a3c969 |
| `dragon-fodder.raw.json` | `2ab400e18db9685930a5b0e2421a3852eb132844363da5cb55d0f60ba0158854` | https://api.scryfall.com/cards/f9abe517-f601-4784-8d62-2350bd755146 |
| `lightning-bolt.raw.json` | `282dd8fb3b7527aecd13fdc32134ba72c18940d687b081f318fa484dd0988dee` | https://api.scryfall.com/cards/7673784e-db4b-43a1-8d55-1bb9fc1e284f |
| `stifle.raw.json` | `5dbae174f172bdad7665ca37402d384823f4daa23639218a66e4de0a7fd49eb3` | https://api.scryfall.com/cards/616d1b20-61c1-4d39-a9b5-ad9fd61699e4 |
| `thalia.raw.json` | `34000655d68e960243cf5ac25749bfd113e3451b05af78d6111a490e2bc97163` | https://api.scryfall.com/cards/c9f8b8fb-1cd8-450e-a1fe-892e7a323479 |

The tests separately label adversarial grammar and trusted zone-transition
probes. Those probes are not alternate canonical Oracle text or certificates of
full card, arbitrary-card, HTTP or browser support. Existing full canonical
Lithoform Engine and Unsummon fixtures are reused rather than rewritten.
