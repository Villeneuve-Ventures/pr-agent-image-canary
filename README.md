# PR-Agent image canary

Public synthetic fixtures and reviewed generic workflow code for an exact-image canary. No private repository source, instructions, credentials or quota/account commentary is included.

The image is a locally qualified Linux amd64 artifact from public PR-Agent source `981344be2755e303df501e18e3f60b848a188a80` with recorded dependency repairs. No build runs in this repository. Publication copies existing OCI bytes with digest preservation.

The native `/prreview` alias forwards to upstream `/review`. Native review publication may be an issue comment with cached head/state attribution, not a GitHub review object with `commit_id`; it does not add a fresh prepublication stale-head guard. Canary observations must retain that distinction. No production merge or enablement is authorized by this repository.

See the accompanying upstream license notice. The publication evidence records source and dependency provenance; it does not claim byte-for-byte rebuild reproducibility or vendor endorsement.
