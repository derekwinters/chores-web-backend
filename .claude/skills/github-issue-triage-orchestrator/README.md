# github-issue-triage-orchestrator

Main orchestrator agent for GitHub issue triage workflow. Implements state machine to track issue through complete validation and labeling.

## Usage

```
/triage-issue <issue-number>
```

## State Machine (9 states)

1. **categorize** (auto) - Run #144, detect type + complexity
2. **check-duplicates** (auto) - Run #148, find related issues
3. **validate** (auto) - Run validator (#145-147 per type)
4. **feedback** (auto, conditional) - If invalid, run #149, post user comment
5. **[PAUSE]** - Wait for user to provide missing info
6. **validate** (re-run, auto) - Verify completeness after user response
7. **apply-labels** (auto) - Run #150, apply all labels
8. **suggest-milestone** (auto) - Run #151, suggest milestone
9. **complete** - Issue fully triaged

## Automatic vs User-Involved

**Fully Automatic**: categorize, check-duplicates, apply-labels, suggest-milestone

**User Involved When**: Validation fails → user provides info → re-validate → continue

## State Tracking

State persisted in pinned bot comment on issue:
```
@bot-triage-status
Current State: apply-labels
Progress: 7/9
History: categorize ✓ → check-duplicates ✓ → validate ✓ → feedback ✓ → validate ✓
```

## Integration

- Orchestrates all skills (#144-151)
- Invoked: manually (`/triage-issue <number>`) or webhook
- Returns: Fully triaged issue with labels + milestone suggestion
