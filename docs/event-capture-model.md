# Event capture model

> A macro-free spreadsheet cannot reliably auto-append an immutable event every time a user changes a cell.

The workbook therefore does not try. It records R1 events through a controlled, visible process instead.

## The four parts

1. **Controlled event entry or import.** A person appends one row to `tblEventLog` for each material change, or imports rows produced elsewhere. Rows use the exact ten-column shared event contract; `payload` holds the event's JSON object as text.
2. **Registered event mappings.** `config/event-mappings.yaml` lists which workbook change corresponds to which registered R1 event (17 mappings), the event subject, and where each required payload field comes from. Only event types in the pinned R1 catalog are allowed, and no scenario-pack event is used.
3. **Reconciliation warnings.** Every record table has an `event_evidence` column. For each material change at or after `event_reconciliation_from_at`, it looks for the matching event row and shows `logged` or `missing:<event type>`. Changes before the window show `before_window`.
4. **Export validation.** The Event Log's check columns verify each row's event type and subject type against the R1 catalog (`event_type_check`), the producer (`source_repo_check`), the actor (`actor_check`: a `PER-` person for human actors, a configured R1 rule for system actors, never an AI actor in v0.1), the subject's existence (`subject_check`), the payload's shape (`payload_check`), and, for request status changes, the legality of the transition (`request_transition_check`). `tools/validate.py` then parses every payload as JSON and validates the JSONL export against the shared event schema.

## Who produces the events

Every event in the workbook is an R1 event, recorded in R1's spreadsheet implementation, so `source_repo` is always `implementation-operating-system`. The workbook (R3) produces no events of its own.

## What the bundled data shows

R1's synthetic event file is a deterministic sample of 38 events, not a complete audit log. With the reconciliation window starting at `2026-09-01T00:00:00Z`, the workbook flags 27 material changes in the synthetic data that have no event row (for example the completion of `TSK-000002` and `TSK-000003` in Synthetic Project A, and the submission of `REQ-000001`). These flags are the control working as designed: in live use, each would be appended. The Event Log itself has 0 failing rows.

## Honest limits

- Nothing stops a person from editing or deleting an event row. Immutability is a property of the process, not of the spreadsheet.
- The workbook cannot know the previous value of a cell, so `from_status` in a status-change event is written by the person, and checked only for request transitions.
- Reconciliation shows that a matching event exists, not that its payload matches every field; `tools/validate.py` checks payloads on export.

## What later software could automate

A database-backed implementation of R1 could append events transactionally on every change, capture previous values automatically, enforce request transitions at write time, sign or hash the event stream, and reject edits to past events. The workbook intentionally automates none of these, and states so rather than imitating them.
