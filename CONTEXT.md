# Chores Web

A household chore tracking app where people earn points for completing chores.

## Language

**Chore**:
A repeating household task with a schedule, assignment strategy, and point value.
_Avoid_: Task, item, job

**Completion**:
The event of a person marking a Chore as done, awarding points and advancing the schedule.
_Avoid_: Finishing, doing

**Assignee**:
The person currently responsible for completing a due Chore.
_Avoid_: Owner, user

**Credit**:
The attribution of points to a person for a Completion. Stored in the Points Log.
_Avoid_: Award, score

**Amendment**:
An admin correction to a Points Log entry that adjusts the credited person or point value of a past Completion.
_Avoid_: Edit, fix, reassignment (when referring to post-completion credit change)

**Completer**:
The person who physically performed a Chore. For Chores without an Assignee (`current_assignee === null`), the Completer is specified explicitly at Completion time via a required modal. The Completer receives the Credit, not the logged-in user.
_Avoid_: Doer, performer

**Reassignment**:
Changing the Assignee of a due (not yet completed) Chore. Does not affect the Points Log.
_Avoid_: Transfer (when referring to a pre-completion assignee change)

**Points Log**:
Append-only record of all Credits. One entry per Completion.
_Avoid_: Score log, history

**Activity Log**:
Unified audit trail of all chore events: completions, skips, reassignments, amendments, and config changes. Backed by ChoreLog and UserLog merged at query time.
_Avoid_: Event log, audit log, history

**Notification**:
A per-person record that a Chore became due. Generated server-side by the scheduled due-transition job, one per relevant person per Chore it flips to due. v1's only server type is `chore_due`.
_Avoid_: Alert, reminder, message

**Delivery**:
The server-recorded event of a Notification first being returned to a client (`delivered_at`). The server owns delivery state; a Notification is delivered at most once.
_Avoid_: Send, push, fetch

**Acknowledgement**:
The person's explicit confirmation of a Notification (`acknowledged_at`). An acknowledged Notification is never dismissed by the server.
_Avoid_: Read, seen, confirm (as a bare verb)

**Dismissal**:
Server-side retirement of a stale, unacknowledged Notification whose Chore is no longer due (`dismissed_at`). A Notification dismissed before Delivery is never delivered.
_Avoid_: Delete, clear, expire

**Notification Preference**:
A person's per-type opt-out from Notifications. An absent row means enabled; a row exists only to record an explicit choice, and generation skips a person only when a row exists with `enabled = false` for that type.
_Avoid_: Setting, subscription, mute

## Relationships

- A **Chore** produces one **Points Log** entry per **Completion**
- A **Completion** produces one **Activity Log** entry with action `completed`
- An **Amendment** appends one **Activity Log** entry with action `amended` without modifying the original `completed` entry
- A **Reassignment** applies only to due Chores and never touches the **Points Log**
- A **Completer** is the Assignee when `current_assignee` is set; when `current_assignee === null`, the Completer is selected explicitly at Completion time
- A **Chore** flipped to due by the scheduled job produces one **Notification** per relevant person (the Assignee, or every eligible person for an open Chore), skipping anyone with a disabling **Notification Preference**
- A **Notification** progresses through **Delivery** and either **Acknowledgement** (by the person) or **Dismissal** (by the server when its Chore is no longer due and it was never acknowledged)

## Example dialogue

> **Dev:** "If we move credit from Alice to Bob, should we update Alice's `completed` entry in the Activity Log?"
> **Domain expert:** "No — Alice did complete the chore. The Amendment records the credit transfer separately. The original `completed` entry is preserved."

## Flagged ambiguities

- "reassigned" appears in two senses: (1) changing who will do a due Chore — this is a **Reassignment** — and (2) changing who gets credit after Completion — this is an **Amendment**. These are now distinct terms with distinct `action` values in the Activity Log.
