
# AI Usage Disclosure

## 1. AI Tools Used

ChatGPT was used as a development assistant during the implementation of TraceGuard.

Its assistance included:

- Breaking down the assessment requirements into an implementation plan.
- Discussing project architecture and separation of responsibilities.
- Assisting with Python implementation and code structure.
- Identifying potential edge cases in financial reconciliation.
- Helping design unit tests and property-based tests.
- Debugging test failures and implementation issues.
- Reviewing evidence tracking and failure-handling behavior.
- Assisting with project documentation.

## 2. One Useful AI-Generated Suggestion

One particularly useful suggestion was to use property-based testing to verify invariants rather than relying exclusively on individual example-based tests.

This led to tests checking that:

- Changing event processing order does not change the result.
- Adding identical duplicate events does not change financial totals or status.
- Changing support-note text does not affect financial truth.
- Adding unrelated tenant records does not change another tenant's investigation result.

These tests helped verify important properties of the reconciliation system.

## 3. One AI-Generated Suggestion That Was Rejected

An approach involving LLM-based interpretation of financial records to determine payment status was rejected.

Financial calculations and payment status decisions must remain deterministic and reproducible.

An LLM could introduce uncertainty or be influenced by malicious instructions embedded in support notes.

Therefore, financial reconciliation was implemented using deterministic Python logic. AI assistance was limited to development guidance, code review, debugging, and documentation.

## 4. Human Review and Responsibility

AI-generated suggestions and code were reviewed during implementation.

The developer ran the application, executed automated tests, investigated failures, and verified representative scenarios.

Final implementation decisions, testing, and assessment submission remain the developer's responsibility.

## 5. Core Principle

AI can assist with software development, but financial truth must come from validated records and deterministic rules.
