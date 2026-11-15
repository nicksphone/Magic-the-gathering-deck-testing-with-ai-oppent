# Variable-X library search

The complete variable-search instruction binds its mana-value maximum to the
announced X, including zero. Type, count, destination, reveal and tapped-entry
restrictions come from the printing. Unsupported trailing grammar remains
unsupported.

Client search-override annotations cannot replace the printed restrictions.
The library filter uses the mana-value helper, including explicit colorless and
hybrid symbols and treating X/Y as zero in a library.

The regression scenarios cover bounds, zero-cost creatures, countering, copies,
convoke, trusted free-effect casting at X zero, current and restored human/AI
choices, caller/RNG preservation and atomic rejection of client overrides.
Operand/compiler diagnostics do not establish universal library-card eligibility.

## Tests

From `backend/`:

```sh
python -m pytest -q tests/test_variable_library_search.py
```

## References

- [Wizards Ravnica Remastered release notes](https://magic.wizards.com/en/news/feature/ravnica-remastered-release-notes)
