# Graveyard source characteristics and copy semantics

Lexical markers in printed card text are review aids, not semantic
classifications. Neither the presence nor absence of a word establishes an
ability's operating zone, engine support or playing strength. Missing layout or
characteristic metadata must not be guessed from a source inventory.

A conditional graveyard-copy ability must preserve its activation condition,
payment, legal target and source references, copiable values, later effects and
counters, cleanup, last-known information, zone changes and snapshot behavior.
Copying an existing permanent does not create an entry event.

Copy-record consumers must avoid aliasing mutable effect history. Printed
restoration follows last-known-information capture; counter cleanup on departure
is a separate operation. Serialization must retain the required fields rather
than infer missing history.

The Modern Horizons 3 release notes describe the copying ability's activation
cost, lack of an entry event, retention of existing effects/counters and use of
the graveyard card's printed characteristics.

See [conditional graveyard self-copy](conditional-graveyard-self-copy-20261110.md).

## References

- [HTML release notes](https://magic.wizards.com/en/news/feature/modern-horizons-3-release-notes)
- [security advisory](https://github.com/vitejs/vite/security/advisories/GHSA-8g5g-mxqh-grgj)
- [canonical roadmap issue2](https://github.com/nicksphone/Magic-the-gathering-deck-testing-with-ai-oppent/issues/2)
