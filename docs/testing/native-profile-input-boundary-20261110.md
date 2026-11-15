# Evidence input-boundary correction

An earlier evidence catalog incorrectly classified native-only
knowledge-profile inputs as available to tooling reads, copies and hashes.
The earlier body-exclusion claim is invalid. A later correction does not
retroactively qualify those operations.

The correction excludes the normalized profile-directory prefix before
consulting either the positive catalog or Python membership. Normalization is
necessary because redundant separators and dot components can otherwise bypass
a raw-string prefix check.

Tooling uses ordinary file metadata and reference symlinks for these inputs.
The original native reader retains responsibility for body access and its
content-integrity check. This separation concerns evidence tooling, not a
change to gameplay rules.
