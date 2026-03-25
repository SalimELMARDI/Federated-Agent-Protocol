# Local KB Example Data

This directory contains the default local knowledge-base files used by `participant_kb`.

`participant_kb` loads entries from disk through the `PARTICIPANT_KB_PATH` environment variable. If the variable is not set, it defaults to:

```text
examples/local_kb/data
```

Supported file formats in this first connector version:

- `.json`
- `.md`
- `.txt`

Supported JSON shape:

```json
{
  "entry_id": "kb-001",
  "topic": "Privacy controls",
  "content": "Knowledge-base notes about governed sharing."
}
```

Text and markdown entries derive `entry_id` from the filename. Markdown uses the first `# Heading` as the topic when available. Otherwise the filename suffix after `__` becomes the topic.

Search remains deterministic:

- case-insensitive
- matches on `topic` or `content`
- stable ordering by filename
