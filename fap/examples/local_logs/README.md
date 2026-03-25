# Local Logs Example Data

This directory contains the default local log files used by `participant_logs`.

`participant_logs` loads log data from disk through the `PARTICIPANT_LOGS_PATH` environment variable. If the variable is not set, it defaults to:

```text
examples/local_logs/data
```

Supported file formats in this first connector version:

- `.json`
- `.log`
- `.txt`
- `.md`

Supported JSON shape:

```json
{
  "event_id": "log-002",
  "source": "privacy-monitor",
  "message": "Privacy monitor event recorded.",
  "level": "warn"
}
```

Text, log, and markdown files derive:

- `event_id` from the filename
- `source` from the filename suffix after `__`
- `message` from the file content
- `level` from a simple content heuristic

Search remains deterministic:

- case-insensitive
- matches on `source` or `message`
- stable ordering by filename
