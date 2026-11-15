# Isolated Operator Profiles

The native engine/AI are Forge Team/Card-Forge work. Retain [the original
notices](NOTICE.md), [cost-increment notices](known-mana/NOTICE.md) and GPL license.
These helpers derive opt-in metadata; they do not enable or deploy a runtime.

`runtime_profile.py` accepts only the qualified base build and its exact complete
launch command. It preserves that sandbox/command, prepends the approved shadow
read-only, and assigns a separate content-addressed build identity. Moving a
shadow, changing source/class bytes or changing the qualified base requires new
qualification. No base checkpoint is relabelled as a new-build save.

For the current guarded known-mana candidate, first build the three sources
with [its additive builder](empty-source/README.md), then use:

```sh
python3 tools/engine_evaluation/forge/native-ai/runtime_profile.py \
  /absolute/qualified/base-runtime.json \
  /absolute/qualified/BUILD-IDENTITY.json \
  /absolute/new/local/candidate \
  /absolute/new/local/profile \
  tools/engine_evaluation/forge/native-ai/empty-source/profile-bundle.json
```

The committed approval lists exactly three source and four emitted class hashes,
including `ComputerUtilCost$1`. No additional artifact path or hidden class is
approved. The optional fifth argument is trusted operator input, never browser
or checkpoint data. Supplying JSON null does not select the older single-class
mode. Omitting it selects the separately frozen identity-only candidate, whose
earlier test/game history is independent.
The earlier `known-mana-profile-bundle.json` remains the frozen pre-empty-guard
approval and must not be relabelled as the current candidate.

Publication requires a fresh output directory and no symlink inputs. Both files
are staged through private directory descriptors, flushed and published with a
no-replace rename. A changed parent or competing output/staging directory does
not permit redirected writes or cleanup of someone else's directory. A directory
fsync failure after rename can leave a complete profile with uncertain durability;
inspect that failure instead of blindly retrying or deleting it.

Additional trusted bundle schemas require complete compositions: schema 2 adds
the actor boundary (four sources/six classes), schema 3 adds damage timing
(five sources/seven classes), and schema 4 additionally requires the shared
damage policy (six sources/eight classes). A schema number never authorizes
missing, extra or changed payloads. Each actual composition still requires its
own reviewed source/class hashes and native qualification.

Twenty-two labelled synthetic tests cover this metadata boundary. Native cost
qualification and actual built-app qualification are separate, documented in
[the current knowledge-boundary status](../../../../docs/testing/native-ai-knowledge-boundary.md).
Neither a successful profile derivation nor its test count proves broad AI
fairness, playing strength, app cold-resume or release readiness.
