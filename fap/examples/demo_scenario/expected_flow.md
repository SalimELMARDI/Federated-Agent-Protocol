# Expected Demo Flow

## 1. Create
- `create_task.json` is posted to `POST /messages` on the coordinator.
- The coordinator parses the canonical `fap.task.create`.
- The run is created in the in-memory store.
- The raw canonical message and latest run snapshot are persisted.

## 2. Evaluate
- One-shot orchestration calls:
  - `participant_docs /evaluate`
  - `participant_kb /evaluate`
  - `participant_logs /evaluate`
- Participant order is fixed:
  1. `participant_docs`
  2. `participant_kb`
  3. `participant_logs`
- Because `requested_capabilities` is empty, each participant accepts using its full capability profile.
- The coordinator records and persists each returned `fap.task.accept`.

## 3. Execute
- The coordinator dispatches `POST /execute` only to accepted participants.
- Each participant performs deterministic local execution using the shared `input_query="privacy"`.
- Current governed execution outputs are:
  - `participant_docs` => `[SUMMARY ONLY] Matched docs: Privacy Policy Memo`
  - `participant_kb` => `[SUMMARY ONLY] Matched KB entries: Privacy controls`
  - `participant_logs` => `[SUMMARY ONLY] Matched log events: privacy-monitor`

## 4. Policy Attest
- Each participant applies the shared policy engine using the inbound governance:
  - `privacy_class=internal`
  - `sharing_mode=summary_only`
  - `policy_ref=policy.demo.v0`
- Each participant returns a canonical `fap.policy.attest`.
- The attestation preserves the same `task_id`, `run_id`, and `trace_id` as the originating run.

## 5. Aggregate Submit
- Each participant also returns a canonical participant-originated `fap.aggregate.submit`.
- The aggregate submission:
  - preserves the same `task_id`, `run_id`, and `trace_id`
  - uses `contribution_type="summary"`
  - uses the governed summary as `summary`
  - uses the returned `policy_attest.message_id` as `provenance_ref`
- The coordinator records and persists all returned aggregate submissions.

## 6. Aggregate Result
- After execution, the coordinator aggregates the recorded `aggregate_submissions`.
- Aggregation mode is `summary_merge`.
- Ordering is deterministic by `participant_id`.
- The final answer is:

```text
[participant_docs] [SUMMARY ONLY] Matched docs: Privacy Policy Memo
[participant_kb] [SUMMARY ONLY] Matched KB entries: Privacy controls
[participant_logs] [SUMMARY ONLY] Matched log events: privacy-monitor
```

- The coordinator records and persists a canonical `fap.aggregate.result`.

## 7. Persistence And Inspection
- `GET /runs/{run_id}` shows the latest run projection, including:
  - decisions
  - completions
  - policy attestations
  - aggregate submissions
  - aggregate results
- `GET /runs/{run_id}/events` shows persisted protocol events in durable order.
- Expected event type order for the happy-path demo:
  1. `fap.task.create`
  2. `fap.task.accept`
  3. `fap.task.accept`
  4. `fap.task.accept`
  5. `fap.task.complete`
  6. `fap.policy.attest`
  7. `fap.aggregate.submit`
  8. `fap.task.complete`
  9. `fap.policy.attest`
  10. `fap.aggregate.submit`
  11. `fap.task.complete`
  12. `fap.policy.attest`
  13. `fap.aggregate.submit`
  14. `fap.aggregate.result`
