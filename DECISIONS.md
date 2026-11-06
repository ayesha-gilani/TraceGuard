
# TraceGuard — Engineering Decisions

## 1. What was the most dangerous assumption in this problem?

The most dangerous assumption was treating individual records as independently trustworthy.

An order record, payment event, and support note may describe different versions of the same transaction. A successful payment attempt can coexist with an earlier failed attempt, and duplicate or delayed events can make a transaction appear inconsistent.

Another risk is assuming that support notes accurately represent financial state. Support notes may contain outdated information or malicious instructions.

To address this, TraceGuard separates financial evidence from contextual information. Checkout records define the expected order, payment records establish financial activity, and support notes cannot override either.

## 2. Which part must never depend on an LLM, and why?

Financial reconciliation must never depend on an LLM.

Payment amounts, refunds, transaction identities, currencies, and final payment statuses require deterministic and reproducible calculations.

An LLM may produce inconsistent interpretations of the same records or follow instructions embedded in untrusted support notes.

TraceGuard therefore uses deterministic Python logic for financial calculations and status determination. No paid LLM API or external model is required.

## 3. When is UNKNOWN the correct answer?

UNKNOWN is appropriate when the available evidence cannot establish a reliable financial outcome.

Examples include:

- Missing checkout order definition.
- Conflicting checkout amounts or currencies.
- Invalid financial timestamps.
- Conflicting event identities.
- Capture amounts exceeding the expected order amount.
- Refunds referencing unknown captures.
- Refund totals exceeding the original capture.
- Missing essential records because a required tool failed.

Instead of guessing, TraceGuard returns UNKNOWN, records relevant anomalies, and preserves the available evidence IDs.

This is safer than reporting an incorrect PAID or REFUNDED status.

## 4. What was the hardest bug, and how was it verified?

One important issue involved evidence traceability during failed reconciliation.

Initially, capture and refund event IDs were added to the evidence list only after financial validation succeeded. Consequently, an investigation could return UNKNOWN because of an invalid capture without including that capture's event ID in the final evidence list.

I corrected this by recording payment event IDs before processing their financial details.

The correction was verified using an over-capture scenario. The result remained UNKNOWN, while its evidence list included both the checkout event and the offending capture event.

Additional verification was performed through the complete automated test suite and a normal successful payment investigation.

## 5. Which AI-generated suggestion was rejected, and why?

An approach that would allow an LLM to interpret payment records and determine the final financial status was rejected.

Although an LLM could make explanations sound more natural, allowing it to determine payment truth would introduce unnecessary uncertainty into financial calculations.

It could also be influenced by malicious instructions in support notes.

I retained deterministic reconciliation and used structured explanations instead. This also avoids dependence on paid API credentials.

## 6. What would break first at one million events per day?

The current in-memory repository would be the first major architectural limitation.

Keeping the entire event history in memory would become inefficient as event volume and retention requirements increase.

A production-oriented version would need:

- Persistent database storage.
- Indexed tenant and order lookups.
- Streaming or batch ingestion.
- Efficient event deduplication.
- Appropriate partitioning and retention policies.
- Monitoring and performance testing.

The reconciliation logic would also need performance evaluation under realistic workloads.

## 7. What would be improved with one additional day?

I would prioritize the following improvements:

1. Add more malformed and contradictory event scenarios.
2. Expand testing for transaction identity conflicts and incomplete histories.
3. Improve structured logging and diagnostic output.
4. Add performance benchmarks for larger event datasets.
5. Improve the investigation explanation layer while keeping financial decisions deterministic.
6. Add persistent storage and a more realistic external tool integration.

The highest priority would remain correctness, traceability, and reliable failure handling rather than adding unnecessary interface features.

---

## Final Engineering Principle

TraceGuard follows one central principle:

**When financial evidence is inconsistent or insufficient, preserve the evidence and return UNKNOWN rather than inventing certainty.**
