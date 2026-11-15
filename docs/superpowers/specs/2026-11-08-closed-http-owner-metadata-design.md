# Closed HTTP Owner-Lock Metadata

The closed-runtime test archiver currently hashes and copies every regular file.
That violates the existing protected-body rule when a closed fixture retains its
capacity-owner lock. The ongoing RC goal authorizes this reversible correction;
the behavior is determined by that existing rule, with no new product choice.

My implementation choice is to inventory an empty, single-link, mode0600 regular
owner lock as metadata only, omit its tar payload and report the omission
explicitly. Other protected model names fail closed before body access. Unsafe
lock metadata also fails closed. Existing closure, root ownership, inode, archive
pin, byte verification, failure retention and final cleanup checks remain.
Tar creation also rejects members absent from the first inventory before their
bodies can be opened, including protected names added between inventory and tar.

Failing all owner-lock archives would leave the valid cold fixture unusable.
Removing archive verification would discard required evidence. Neither meets the
existing goal; metadata-only handling preserves it. This choice is mine under
the established constraints, not a new user preference or scope waiver.

Tests create only new empty synthetic protected files, deny body opens through
audit hooks, inspect real tar/inventory/receipt results and verify late metadata
replacement prevents deletion. Existing public fake payloads and inert process
fixtures remain real filesystem tests, with no native app, SQL or network.
No real operator lock/model/database or private game body is examined.
