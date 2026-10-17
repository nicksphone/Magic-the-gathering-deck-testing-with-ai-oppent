# Published A32 Hosted Browser Result

GitHub run `38996831054`, attempt 1, is bound to published
`a32dbd0d67586d5f6e4d5dcea2ec8860ff9ee550`. Browser job `117291129305`
starts at 2026-10-17 02:56:03 UTC and completes successfully at 03:36:02 UTC.
The frontend job also succeeds. The backend job is still in progress at the
04:20 UTC observation; no whole-workflow success is claimed.

Before reading the public browser log, the exact published workflow is checked:
there is no workflow-wide secret environment, and the browser job has no
protected witness or secret binding. Its workflow SHA256 is
`5e329085b04edf45dc8ed60667dc87fa738e38cc2f9d862359fc76588d164fff`.
The job log is 116,960 bytes with SHA256
`72e928ffccdeae47058db8150d0fd4bf1ae033961f39d336a6fd040208a5c4a0`.

The run-level CLI initially refuses logs while the backend is still running.
That zero-byte retrieval stop is preserved. The subsequent exact public
browser-job API supplies only this completed job's log. No raw backend log or
protected trace is read or published.

The complete metadata, published workflow, public log and retrieval history are
archived with forward byte/mode/link verification under the project's NFS
diagnostics directory, `a32-public-browser-SUCCESS-20261017-042031`.

This configured hosted lane sets `MTG_BROWSER_NO_SANDBOX=1`. Its success does
not qualify native sandboxed Chrome/Brave/Firefox, LAN HTTPS or a selected live
deployment. Nor does it establish the cause of an earlier browser failure,
complete the backend job or sign off Phase 1 or RC.
