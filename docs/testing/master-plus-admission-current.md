# Master+ request admission

Base: published af75a81, including either-human-seat setup.

The UI, AIAgent and batch request already support master_plus. Match-start and
AI diagnostics instead admitted only three difficulties. Both public request
literals now also admit master_plus; defaults and all other fields are unchanged.
No alias, downgrade, new policy, search-depth change or dependency was added.

The NEW whole 19-case model/policy module reproduced three original admission
failures (both human seats and diagnostics), with 16 controls passing. After the
two literal changes all 19 passed. It uses actual main.StartMatchRequest and
analytics request models, roundtrips the public payload, rejects unknown/null/
boolean difficulties, and checks the existing distinct Master+ policy horizon.
The precollection audit hook denied all native SQLite connections and sockets;
the observed violation ledger was empty and no source-local database existed.
Importing main generated its genuine owned fallback media cache, not a database.

This proves request-model admission and unchanged policy selection, not actual
HTTP match creation, diagnostics completion, Master+ gameplay quality or the
full current built-app gate. Those remain separate release qualifications.
