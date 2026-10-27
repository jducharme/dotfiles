# Spec NNN: <title>

status: draft <!-- draft → ready (approved by the user) → in-progress → in-review → done -->
created: YYYY-MM-DD · owner: <name> · branch: `spec/NNN-slug`
areas: <!-- the directories or components this touches -->

## 1. Why
<!-- The problem, in the user's words where possible. Who hits it, and what happens today. -->

## 2. Outcome
<!-- One or two sentences: what is true once this ships. -->

## 3. Scope
### In scope
-
### Out of scope
<!-- Reviewers flag anything here, or anything not in "in scope", as spec drift. Be explicit. -->
-

## 4. Acceptance criteria
<!-- Each one observable and testable. Reviewers grade every AC: met / partial / not_met / untestable.
     Name tests after the AC: it('AC-2: …'). Mark an AC "verify: manual" only when it really can't be automated. -->
- **AC-1**: Given …, when …, then …
  - verify: `<test file>` → `AC-1: …`
- **AC-2**:
  - verify:

## 5. Design notes
<!-- The approach agreed in conversation, constraints, files likely touched, interface or schema changes,
     env vars. Enough that a reviewer can tell intended design from accidental design. -->

## 6. Test plan
<!-- Unit / integration / manual. Which ACs each covers. Edge cases worth a test. -->

## 7. Security, privacy & compliance
<!-- Tick what applies and say how it's handled. Reviewers check these against the repo rules. -->
- [ ] Sensitive data (personal, customer or regulated data): what reaches an LLM or a log, and how it's kept out
- [ ] Secrets / env vars: new ones are documented, never committed
- [ ] Anything sent outside this machine (a new service, URL or CLI)
- [ ] None of the above

## 8. Open questions
<!-- Anything the author inferred rather than the user agreed goes here. Empty, or each item marked "deferred: …",
     before status can move to ready. -->
-
