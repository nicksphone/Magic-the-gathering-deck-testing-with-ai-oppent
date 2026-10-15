# Firefox Transport Integration

The browser test infrastructure now includes the existing WebDriver BiDi
transport and private response-cache protocol as repository-owned source.
This is a transport/driver component, not current native Firefox acceptance.
Neither the default launcher nor browser discovery silently substitutes Firefox
for Chromium or vice versa.

## Existing Contracts

`firefox-transport.mjs` retains the reviewed enrollment, getter and future-child
registration mechanisms from the older private Firefox application harness.
Response bytes remain in an owned mode-0700 local directory with mode-0600
files, real producer identity, nonce/source/context binding, fixed expiry and
actual native continuation acknowledgments. The test-only ASGI cache preserves
the original `BodyCache` class and constants; its explicit factory validates
caller bindings before importing the genuine application fixture.

Both existing JavaScript drivers accept a once-bound transport. They preserve
the original CDP path when no transport is bound, never fall back to CDP after
a malformed Firefox result, and close owned native pages after initialization
or diagnostic-finalization failures. Native iframe readiness must come from
the transport's validated registration receipts. `Target.setAutoAttach` remains
an explicit capability hold rather than fabricated debugger events.

The additional command mappings use real BiDi navigation, activation, preload
and network-interception commands. Native URL blocking is not a successful
no-op. Fetch disabling drains owned blocked requests and joins actual pending
acknowledgments. Preload scripts and owned native registrations are removed on
closure. Unsupported options continue to reject.

## Local Verification

```bash
npm --prefix frontend run test:unit:firefox
python3 -m unittest discover -s backend/tests -p test_firefox_response_cache.py -q
```

These controls use inert native-wire replies, synthetic ASGI messages and
owned temporary files. They do not start Firefox, application listeners or
SQLite, and do not certify a native browser or a complete game. The genuine
positive factory startup remains a separate integration requirement.

## Remaining Native Work

The current full zero-argument browser launcher still needs Firefox-specific
launch/readiness and cache lifecycle integration, including its independently
launched programs. The existing async-readiness `data:` document is still
explicitly unsupported by the transport, and enrollment still uses the older
BO3 episode contract. These gaps must be handled explicitly, not hidden by
dropping scenarios, broadening untested permissions or using Chromium.

The older [50-case Firefox application result](firefox-native-application50.md)
retains its separate outer identity-observation hold. This code port does not
erase that evidence gap or transfer its source-specific runtime result.
