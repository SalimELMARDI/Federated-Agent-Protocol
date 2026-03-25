# Local Docs Example Data

This directory contains the default local document files used by `participant_docs`.

`participant_docs` loads documents from disk through the `PARTICIPANT_DOCS_PATH` environment variable. If the variable is not set, it defaults to:

```text
examples/local_docs/data
```

Supported file formats in this first connector version:

- `.json`
- `.md`
- `.txt`

Supported JSON shape:

```json
{
  "doc_id": "doc-002",
  "title": "Privacy Policy Memo",
  "content": "Local policy notes for privacy review."
}
```

Text and markdown entries derive `doc_id` from the filename. Markdown uses the first `# Heading` as the title when available. Otherwise the filename suffix after `__` becomes the title.

Search remains deterministic:

- case-insensitive
- matches on `title` or `content`
- stable ordering by filename
