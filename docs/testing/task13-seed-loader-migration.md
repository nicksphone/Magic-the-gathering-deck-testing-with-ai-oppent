# Task1.3 seed-loader migration

Base: `2eeb7f769aa8b2a02e0b6e4cb14dc98ecf7f8e17`. Isolated source only; parent owns publication and broader qualification.

`card_data/seed_cards.py` now exposes `SEED_CARD_DATA` and `seed_card_payload`; the former `fallback_cards.py` is removed. Lookup normalization, canonical/front aliases, None for unknown names, shared payload shapes and every existing seed field are preserved. Production, scripts, tests, monkeypatch targets, embedded imports and guard module bindings use the seed API. Every changed existing file is inverse byte-equal after the finite identifier/path substitutions. No rules, metadata, profiles, tactical or scoring formula changes occur.

The complete 155-record seed is unchanged at SHA256 `9296ec1b24654374aaca985b92dc4c3b62a93e6fd024afcd6b4acd61a6007037`; all original card/provenance/fixture JSON/JSONL, historical119 exporter fixtures and raw provenance remain byte-identical. Old test names/branches/assertions/operators/values are retained. The seed is an offline metadata source, not a gameplay or arbitrary-name admission certificate. Existing unknown/incomplete/ambiguous admission and opaque-opponent behavior remain under the same original consumers.

The unchanged original six whole modules passed106 ordinary cases before migration. Adding the new loader contracts first produced169 ordinary failures for the absent API and106 passes. After migration the same seven-module declaration passed275 ordinary cases in6.58s, with0 failures/errors/skips,12 precollection physical native denial canaries, source equality and no unexpected I/O. The private runner relocates only media/database/temp paths, denies every physical SQL/socket/process/provider path and httpx send, and does not start application lifespan or execute HTTP. Runtime is the established read-only Python3.12.3/FastAPI0.115.0/Pydantic2.9.2/pytest8.3.3 environment, not current-lock/fresh-runtime certification. The initial inherited-main-import-fence collection stop is retained separately and is a harness error, not product RED.

Existing mixed SQL/HTTP modules are unchanged except approved import/binding substitutions and remain required as complete modules under a future explicit grant. They were neither selected piecemeal nor run here. Lagrange owns the separate HTTP component. These pure results do not establish full current backend/browser qualification, native matrix, measured A/B or full plan completion.

## Optional operator startup-media binding

The existing `current_built_browser_server.py` reads `runner/startup-media-pins.json` below its separately granted owned root. No approved external artifact was supplied, read or changed. No routine creation helper was found in these immutable committed inputs. The optional operator execution component is therefore held until a parent-reviewed actual artifact and lease exist; this does not block the pure migration.

Its real module tuple changes from `card_data.fallback_cards` to `card_data.seed_cards`; dictionary/lookup names change to the seed API. All frame/global identity, ownership, source/row structural-hash checks and denial branches remain inverse byte-identical. The current required external schema still contains `source_module_pins`, `seed_cards_structural_sha256`, `builtin_decks_structural_sha256`, `expansion_decks_structural_sha256`, and `startup_media`; each startup-media entry still supplies `name`, `type_line`, and `seed_row_sha256`. The external artifact must bind the actual complete finite source map already required by that operator, with affected tuples replaced by their reviewed new path/hash. It must retain its original whole schema/card-media content, never loosen to a prefix, wildcard, partial map or unrestricted fallback. The JSON alongside this document supplies finite migration tuples, not a runtime artifact or execution permission.

| Real module | Before SHA256 | After SHA256 |
|---|---|---|
| main | b341daccb96acb5dac4e6ad8e0244ed13aa6abb5e1c7e4e9d1b69dff6adad452 | 0e163563dfabf109964588d53a2a56504745b032fd56ec44818d5a95258fec9f |
| decks.bootstrap | b968836717698f55e28f0d5b2942209e45ba47d9c67cb3423aa67579274e559b | b968836717698f55e28f0d5b2942209e45ba47d9c67cb3423aa67579274e559b |
| card_data.hydration | 2b415ce61869152a308584fbe33deb7ac04db99a395cb9e311b7a86a4c6a9bbf | a234c5ab0bb4172555a9de8f5a1cbf27bc995a3232b5308bb07d9a6c46c1cc72 |
| card_data.display | f7c584f6bccb22696bc3dfa83563248b6253e597ce87e493924088962c9765eb | f7c584f6bccb22696bc3dfa83563248b6253e597ce87e493924088962c9765eb |
| card_data.placeholders | 44a0ba20815a7204ee2f0332bb5dbd30c648140e78b9cee004aca5ad57acf4df | 44a0ba20815a7204ee2f0332bb5dbd30c648140e78b9cee004aca5ad57acf4df |
| card_data.seed_cards | d0c9d84f0f518deaa6cb28efc7865547896a259935a196ea51eba2607ecb68d5 | cb64ae85690d5239a24895b4ed6ac8a46b5f4c15de64d5bb67192eb187b72c71 |
| decks.expansion_top_decks | df9d1667460859fc21be97ac07c8ae2a02b9980acd9391eb596f526d889b500b | df9d1667460859fc21be97ac07c8ae2a02b9980acd9391eb596f526d889b500b |
| persistence.capacity | fa0aa11cc1da4cdc13a646989fef86d2cda05b43dea9f1d10a1d4078cb5e4bf5 | fa0aa11cc1da4cdc13a646989fef86d2cda05b43dea9f1d10a1d4078cb5e4bf5 |

The old loader path maps solely to `backend/card_data/seed_cards.py`. Unchanged startup role modules retain exact hashes. No old-path re-export remains. Other required source pins in an eventual operator artifact stay mandatory; this table is a reviewed migration tuple list, not authority to discard the operator's remaining pins.
