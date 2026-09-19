# HF-26 — Deep Research: Distributed Systems Correctness & External Effect Semantics for Enterprise Agent Harnesses

**Artifact:** Research Synthesis v0.1 (research only — not an architecture authorization)
**Research ID:** HF-26 · **Project:** HF – Harness Forge · **Date:** 2026-09-19
**Status (final):** `PARTIAL_PROMOTION_EXPERIMENT_REQUIRED` (see Final Verdict)
**Machine-readable appendix:** `docs/hf-research/HF-26-research-appendix-v0.1.json` — mirrors this report exactly (claims, hypotheses, failure classes/scenarios, matrices, decision rules, anti-patterns, profiles, fault-injection tests, promotion decisions, open questions, revision triggers, quality gates).

---

## 0. GOVERNING CONTRACT BINDING & PROVENANCE

| Item | Value |
| --- | --- |
| Contract | PROJECT_OPERATING_CONTRACT **v0.2.2** |
| Digest | `92b8f0b8c4942c8986a21033b8dcfb0ce9f6d8ff9c4b4979ed19d4de95343fe2` |
| Binding check | Treated as immutable for this artifact. |

**Contract version check result:**

* The only contract reference available to this research is the binding stated in the research order itself (v0.2.2 / digest above). **No project material referencing a different contract version or digest was found in the workspace**; therefore `CONTRACT_VERSION_CHANGED` was **not** triggered.
* **Provenance limitation:** the referenced knowledge artifacts (`05 – Runtime, State, Durable Execution & Recovery`, `05.1`, `05.2`, `08 – Lernreihenfolge`, and the Jira `HF-26` ticket) were **not present in the research workspace**. This artifact therefore could not directly challenge or reconcile against those documents. All statements in this report about "current HF hypotheses" are taken from the research order's own framing (e.g., the H1–H10 hypotheses and listed prior learnings) and must be treated as **REVALIDATION_REQUIRED** against the actual artifacts when they are supplied. No conclusions in this report silently reconcile contract or artifact differences.

**Classification of this document:** every material claim carries an Evidence Class and Claim Status per the HF-26 order. Sections 1–12 are research synthesis. Nothing herein authorizes an HF architecture decision; Section "ARCHITECTURE DECISIONS REQUIRING SEPARATE AUTHORIZATION" lists what would need separate sign-off.

---

## 1. RESEARCH METHOD & SOURCE STRATEGY

Method: live web research performed 2026-09-19, following the order's source priority (foundational papers → RFCs/formal specs → official platform semantics → engineering analyses → secondary explanations). ~30 targeted searches across the ten scope domains (A–J). Sources are registered in the **Source Register** at the end (S1…S36) and cited inline as `(S#)`.

Evidence classes used (per order): `PEER_REVIEWED_RESULT`, `FOUNDATIONAL_SYSTEMS_RESULT`, `STANDARD`, `FORMAL_MODEL`, `VENDOR_DOCUMENTED_SEMANTICS`, `ENGINEERING_PRACTICE`, `SYSTEMS_ANALOGY`, `DESIGN_RECOMMENDATION`, `HF_HYPOTHESIS`, `INSUFFICIENT_EVIDENCE`.

Claim status used: `SUPPORTED`, `PARTIALLY_SUPPORTED`, `NOT_SUPPORTED`, `CONTRADICTED`, `EXPERIMENT_REQUIRED`, `INSUFFICIENT_EVIDENCE`.

Known limitations (declared, not hidden):

1. Two foundational items (Gray & Cheriton leases; Kung & Robinson OCC; Garcia-Molina & Salem Sagas) were accessed via reputable summaries/excerpts rather than full-text re-derivation; their content is used only for claims that are uncontested in the literature.
2. The IETF `Idempotency-Key` header work is a **Working-Group draft that expired without becoming an RFC** — it is classified `STANDARD`-track evidence of *proposed* semantics, explicitly *not* an adopted standard (S10, S32).
3. Vendor "exactly-once" claims are decomposed by boundary throughout (Exactly-once Gate); no vendor claim is taken at face value beyond its documented scope.

---

## 2. EXECUTIVE RESEARCH VERDICT

**Research question:** what is the smallest evidence-supported distributed-systems correctness model for enterprise agent harnesses that read, write and cause consequential effects on mutable external systems?

### 2.1 Fundamental (evidence forces these into any correct harness)

1. **Outcome honesty at the effect boundary.** Absence of a success acknowledgement is not evidence of failure (Two Generals impossibility, S8; lost-COMMIT ambiguity, S37/S6; Stripe treats 500s as indeterminate, S11). The harness must distinguish **acknowledgement** from **authoritative outcome** and must carry an explicit `UNKNOWN_OUTCOME` state for consequential effects. This is the single most load-bearing finding.
2. **Effect-class model with per-class retry/identity/reconciliation policy.** "Retry is safe" is a property of the *effect*, not of the transport or the workflow runtime (RFC 9110 idempotent-method semantics, S9; AWS Durable Execution SDK's explicit at-least-once vs at-most-once-per-retry step semantics, S18; Temporal's activity idempotency requirement, S16). A harness cannot be correct without classifying each external effect before deciding retry, identity, and reconciliation behavior.
3. **Boundary discipline for "exactly-once".** Exactly-once can be *implemented* inside a subsystem (Kafka read-process-write loops, S14; Flink state, S15; Step Functions standard-workflow execution starts, S38) but **end-to-end business-effect exactly-once does not exist without idempotency or deduplication in the target system** (S1/S14/S15/S34). HF must ban unscoped exactly-once claims in its own contracts.
4. **Preference for source-native atomic guards over harness-side read-check-write** for source-local invariants: native conditional writes (DynamoDB condition expressions, S30), HTTP conditional requests (RFC 9110 §13, S9), atomic single-statement updates (S31) prove invariants the harness cannot prove from outside. *Boundary:* native guards prove **source-local** invariants only — they say nothing about cross-system invariants or about duplicate-effect identity.
5. **Attempts, receipts and outcome evidence as first-class records.** Every consequential effect needs a durable record of *what was attempted, under what identity, what evidence of outcome exists* (payment-industry practice, S23/S24/S36; outbox practice, S39). This is not a "ledger for everything" (see H5/anti-patterns) — it is a record for *consequential* effects.
6. **Reconciliation as a protocol, not an afterthought.** When outcome is unknown and effects are harmful-if-duplicated, the correct next action is query-then-decide (status APIs, webhooks, settlement evidence — S23/S24), not blind retry and not blind abort.

### 2.2 Conditional (required only under named activation conditions)

* **Stable logical-effect identity + dedup store** — activated when duplicates are materially harmful *and* the source lacks native idempotency, *or* the native dedup window is shorter than the realistic duplicate horizon (SQS FIFO's 5-minute window, S13; Stripe's 24h retention, S11).
* **Lease-based execution authority** — activated when HF itself runs concurrent workers that could act on the same external target. A lease alone does **not** protect the target from a stale holder (Kleppmann, S1; Kubernetes' own leaderelection documentation states it "does not guarantee that only one client is acting as a leader (a.k.a. fencing)", S19). Fencing/epoch checks are required **at the acceptance point** — and most external APIs cannot check fencing tokens, which usually pushes the correct answer to "conditional write at the source" instead of a harness-side lock.
* **Sagas/compensation** — activated only for multi-step flows where each step is individually compensable *by a domain-defined operation*, with the pivot (irreversible step) placed last (S5, S20, S22, S40). Compensation is a new business operation with its own identity, authorization and failure modes — never a technical rollback, never auto-invoked against `UNKNOWN_OUTCOME`.
* **Event Sourcing** — activated when temporal queries/rebuild/projection replay are named requirements. It is *not* required for durable workflow execution (durable runtimes implement their own history internally, S16/S17/S18), *not* sufficient as an audit log by itself (event store ≠ audit log: no third-party verifiability, compaction, external time anchoring — S25), and *not* the only route to provenance (current state + append-only audit trail + receipts is simpler and adequate for most HF needs).

### 2.3 Experimental (candidate mechanisms with weak or bounded evidence)

* Generic HF compensation engine with auto-derived inverses (no evidence that semantic undo can be derived generically; S20 explicitly calls compensation application-specific).
* Automatic reconciliation of cross-system invariants (beyond per-source status queries).
* Effect-ordering guarantees across heterogeneous sources.

### 2.4 Do not promote into HF

* Harness-owned distributed lock managers as a correctness mechanism (Redlock-class; S1, S2 — no fencing, timing-dependent safety).
* A universal "every tool invocation gets an HF ledger entry" requirement (violates minimality; reads and naturally idempotent effects need none).
* Any "exactly-once external effect" guarantee claim in HF contracts.
* Treating workflow-runtime durability as business-effect exactly-once (H1, SUPPORTED).
* Duplicating a source-native guard with a weaker harness-side check and *believing* the harness check adds safety.

**Net answer to the primary question:** the smallest correct model is — *classify the effect; carry identity where duplicates harm; use the source's strongest native guard for state invariants; record attempt/evidence/receipt; represent unknown outcomes explicitly; reconcile before retrying; fence or de-duplicate any authority HF itself grants; compensate only as explicitly modeled domain operations.* Everything else studied (event sourcing, distributed locking, 2PC-class coordination, harness-owned transaction managers) is conditional tooling or an anti-pattern for HF's role as a *client* of authoritative systems.

---

## 3. CANONICAL TERMINOLOGY (HF Canonical Glossary v0.1)

Industry terminology is inconsistent across the studied systems; inconsistencies are flagged explicitly. Definitions are written to be boundary-precise.

| Term | HF canonical definition | Consistency note |
| --- | --- | --- |
| **Attempt** | One execution of an operation by one worker against one target, with a unique attempt identifier. Multiple attempts may target one operation. | Universally used; no major conflict. |
| **Operation** | The logical request to produce an effect, identified independently of any attempt. One operation → many attempts; should map 1:1 to a logical effect. | Stable across literature (Helland "activities", S4; Temporal activity, S16). |
| **Effect** | An observable state change in an external system caused by an operation. Not directly observable by the harness except via evidence (responses, receipts, queries). | Consistent. |
| **Logical effect** | The business-level intended change ("charge invoice 4711 once"), of which physical effects are instances. Distinct from **request identity**: two different requests may carry the same logical-effect identity. | Boundary the industry repeatedly collapses (S36, S24); HF must not collapse it. |
| **Authoritative outcome** | The outcome as determined by the system that executed the effect (its status API, settlement file, event feed) — the only outcome that counts. | Consistent with vendor guidance (S23). |
| **Receipt** | Durable, harness-held evidence of an outcome or attempt: response body, provider object ID, webhook, settlement record. A receipt is *evidence*, not a guarantee. | Term varies ("event", "record"); HF fixes it. |
| **Acknowledgement (ack)** | A transport- or API-level confirmation that a message/call was *received or processed at the interface*, distinct from the business outcome. Ack loss says nothing about outcome (S8, S35). | Messaging systems differ on ack semantics (RabbitMQ/SQS/PubSub); boundary must stay explicit. |
| **Idempotency** | Property of an operation: performing it multiple times has the same observable effect as performing it once (RFC 9110 defines this for methods by *intent*, S9). | RFC phrasing is about intended effect on server; business-level idempotency is stricter and must not be conflated. |
| **Idempotency key** | Caller-supplied identity that lets a *receiver* deduplicate retries of one operation within its retention window (S10, S11). | De-facto standard via Stripe; IETF draft expired (S10). Retention windows differ per provider (24h Stripe vs 5min SQS FIFO vs infinite DynamoDB-conditional patterns). |
| **Deduplication** | Receiver- or harness-side suppression of repeat processing for an already-seen identity. Always window-bounded unless backed by an unbounded store. | Consistent. |
| **Exactly-once (delivery / processing / effect)** | Delivery: message arrives exactly once at an interface (impossible to guarantee across lossy links — Two Generals, S8). Processing: message processed exactly once inside one subsystem (achievable, e.g., Kafka EOS scoped to Kafka-internal loops, S14; Flink state, S15). Effect: business effect occurs exactly once end-to-end (achievable only as *at-least-once + dedup/idempotency at the source of truth* — "effectively once", S15/S34). | HF bans the unqualified phrase. |
| **Effectively-once** | At-least-once execution neutralized by idempotency/dedup so that *observable* effects occur once. Boundary: dedup store/window must outlive the duplicate horizon (S13). | Term used by Flink (S15), Temporal tutorials (S34). |
| **Unknown outcome** | State in which a consequential operation may or may not have produced its effect, and available evidence cannot yet decide. Distinct from failure. (Synonyms in the wild: "in-doubt", "uncertain", "submitted_unknown", "CommitOutcomeUnknown".) | Strongly evidenced across 2PC (S6/S29), payments (S11, S23, S24, S36), DB clients (S37). |
| **Reconciliation** | Protocol that resolves an unknown outcome using authoritative evidence: status query, webhook, settlement/receipt comparison; ends in a decided state or escalation. | Consistent across payments practice (S23/S24). |
| **Transaction** | Atomic, isolated, durable unit of execution **within one system**. ACID atomicity does not span heterogeneous external systems (dual-write problem, S39). | Consistent. |
| **Conditional mutation** | A single atomic source-side operation that mutates only if a stated precondition holds (expected version, ETag, condition expression, `WHERE version = n`). Proves the precondition and applies the mutation atomically (S9, S30, S31). | HTTP calls these "conditional requests"; DBs "conditional updates / compare-and-set". Same invariant class. |
| **Lock** | Mutual-exclusion grant that *advises* holders and contenders; correctness of the guarded resource is only protected if the resource itself rejects non-holders. Without that, a lock is an efficiency tool, not a safety tool (S1, S2, S19). | Contested territory — see lease/fencing. |
| **Lease** | Time-bounded grant of authority that expires automatically (Gray & Cheriton, S3). Correctness depends on the resource rejecting stale holders after expiry. Kubernetes leases explicitly do not fence (S19). | Consistent. |
| **Fencing token** | Monotonically increasing token issued with each authority grant, checked by the *resource* to reject stale holders (S1). Requires resource-side cooperation; generation requires a monotonic source (consensus or a linearizable store). | Kleppmann/antirez agree fencing is needed for correctness-class locks; they disagree on how often that class occurs (S2). |
| **Saga** | Sequence of local transactions T1…Tn with compensating transactions Ci; on failure at Tj, run C(j-1)…C1 in reverse order (Garcia-Molina & Salem 1987, S5). Isolation is *not* provided — interleaving is visible. | Original model vs. modern usage diverge (orchestration/choreography); original semantics retained here. |
| **Compensation** | A **new, forward business operation** that semantically neutralizes a prior effect (refund ≠ undo; email cannot be unsent). Not rollback; not an inverse function; can fail; needs its own identity/authorization/idempotency (S20, S21, S22, S40). | Consistent in all strong sources. |
| **Forward recovery** | Completing the interrupted operation toward its goal (retry/rebind) rather than reversing it; requires the retried steps to be idempotent or identity-guarded (S5 context, S40). | Consistent. |
| **Replay** | Re-execution of recorded logic to reconstruct state (durable runtimes, S16/S17/S18) or re-derivation of state from an event log. Replay of *control logic* is safe only if external effects live outside replayed paths or are identity-guarded. | Consistent. |
| **UNKNOWN_OUTCOME** | HF state-machine state name for the "unknown outcome" concept. | HF-specific; seeded here for reuse. |

---
## 4. EVIDENCE SYNTHESIS BY DOMAIN (A–J)

### A. Delivery and execution semantics

* At-most-once / at-least-once are delivery-and-execution properties of a *subsystem*. Every major system studied documents at-least-once as the default for durability+retries (Kafka producers S14, SQS S13, Pub/Sub S12, Temporal activities S16, Azure Durable Functions S17, AWS durable steps S18).
* **Exactly-once delivery** across a lossy link is impossible (Two Generals; formal statement and proof sketches S8; Tyler Treat position + Kleppmann-adjacent literature S1). **Exactly-once processing** is achievable *within a subsystem*: Kafka transactions give exactly-once for read-process-write loops confined to Kafka (S14); Flink's checkpointing means "every event affects Flink-managed state exactly once" — the docs themselves state this does **not** mean every event is processed exactly once (S15); AWS Step Functions Standard Workflows document an "exactly-once model" for tasks/states (S38), while the newer AWS Durable Execution SDK documents steps as at-least-once with an opt-in at-most-once-per-retry mode and explicitly warns "at-most-once applies per attempt, not per workflow" (S18).
* **End-to-end business-effect exactly-once** requires replayable/transactional or idempotent *endpoints*: Flink states end-to-end exactly-once requires replayable sources AND transactional-or-idempotent sinks (S15); Kafka EOS explicitly does not extend to databases/REST calls (S14); Temporal's own guidance: at-least-once + stable idempotency key = "effectively-once side effects" (S34).
* Acknowledgement loss is the canonical duplicate generator: consumer crashes after side effect but before ack ⇒ redelivery ⇒ duplicate effect (S35; SQS visibility-timeout mechanics S13).

**Boundary conclusion (H9 SUPPORTED):** delivery / processing / effect must always be suffixed. No studied system provides end-to-end effect exactly-once *without* target-side idempotency or deduplication.

### B. Idempotency

* Natural idempotency: RFC 9110 defines GET/HEAD/PUT/DELETE as idempotent by intended effect and warns that non-idempotent methods "SHOULD NOT" be retried automatically (S9). This gives HF a **zero-machinery baseline** for whole effect classes.
* Provider-native keys: Stripe stores first response per key ≥24h, replays it (`Idempotent-Replayed: true`), rejects key reuse with different parameters, and — critically — **replays 500 responses and advises treating 500s as indeterminate because side effects may have occurred** (S11). The IETF Idempotency-Key draft (expired WG draft, not an RFC) specifies key uniqueness, optional fingerprints, 409 for in-flight duplicates, 422 for payload conflicts (S10, S32). AWS Durable Execution SDK mandates generating keys *inside* a checkpointed step so the key survives replay (S18).
* **Request identity ≠ logical business effect identity.** SQS content-based dedup hashes the payload — two legitimate operations with identical payloads collapse, and one operation with two payloads (retried after parameter fix) escapes dedup (S13, S36). Stripe key derivation guidance itself distinguishes random UUIDs from business-derived keys ("ID of a shopping cart") precisely because logical identity matters (S11).
* Retry windows: all native dedup windows are bounded (SQS 5 min, S13; Stripe 24h, S11; Step Functions execution-name uniqueness 90 days, S38). **Delayed duplicates beyond the window are the source's responsibility no longer — F11.** Delayed-duplicate protection must therefore live in the durable, harness-side or source-side *state*, not in the window.
* Counterevidence found (as required): idempotency keys fail to represent business identity when (a) payloads legitimately differ between attempts of one logical operation (replanning changes the payload — key-with-fingerprint rejects; key-without-fingerprint double-fires); (b) different systems mint different request identities for one logical effect (two tabs → two SetupIntents, S41's analysis); (c) windows expire. All three motivate *effect identity chosen at the logical layer* and *unbounded durable dedup* where harm is material.

### C. Optimistic concurrency and conditional mutation

* Read→check→write in application code is a lost-update race by construction (S31: "the read-calculate-write sequence is happening in pieces"; MongoDB's own anti-pattern writeup, S31b). Atomic single-statement updates and conditional writes collapse the window (S31, S30).
* Source-native atomic precondition+mutation exists in every class of system studied: DynamoDB condition expressions (atomic, no capacity consumed on failed condition; version-attribute optimistic locking) — with the documented caveat that **DynamoDB global tables use last-writer-wins, so optimistic locking does not work as expected there** (S30); HTTP `If-Match`/`If-Unmodified-Since` with 412 (RFC 9110 §13 / RFC 7232 text, S9; one-second granularity caveat for date validators, S9a); SQL conditional UPDATE / compare-and-set (S31).
* OCC foundations: Kung & Robinson 1981 formalize validate-at-commit and abort-on-conflict (S7a).
* **Exact boundary of what conditional mutation proves:** the *source-local* invariant "no intervening committed write to the guarded object between the version observation and the mutation". It does **not** prove: (a) that this mutation is not a *duplicate* of an earlier successful one (a retry with the *new* current version will pass the precondition and double-apply non-idempotent mutations — conditional writes need a monotonic effect precondition, e.g., `SET status='paid' WHERE status='unpaid'`, to be duplicate-safe); (b) anything about other systems; (c) anything once the operation returns unknown (the mutation may have happened; a conditional *re*-mutation must be phrased to be a no-op in that case).

### D. Locks, leases and fencing

* Kleppmann's analysis (S1): any lock/lease scheme that relies on time fails when the holder pauses (GC, VM stall, network delay) past expiry and then acts; re-checking the lock before the write cannot fix this (pause can occur between check and write). Safety requires a **fencing token** — monotonically increasing per grant — checked by the resource. Redlock has no fencing mechanism and its safety rests on synchronous-system timing assumptions (bounded delay, bounded pauses, bounded clock error). Antirez's rebuttal (S2): the pause problem is generic to all lease systems; operationally-bounded clocks make Redlock fit for purpose; where fencing matters, add a token check at the resource — and if the resource can do that check-and-set, "it's better to avoid a distributed lock at all" (his own concession, captured in the HN thread S2b).
* Lease origins: Gray & Cheriton 1989 formalized leases as time-based fault-tolerant consistency grants (S3) — leases are clock-dependent by construction.
* Vendor admissions: Kubernetes client-go leaderelection: "This implementation does not guarantee that only one client is acting as a leader (a.k.a. fencing)"; tolerant to clock skew but not to skew *rate*; ReleaseOnCancel must be handled carefully or "you may have two processes simultaneously acting on the critical path" (S19). Kafka's transactional producer exposes `ProducerFencedException` — fencing *is* implemented by the resource (the broker) when the broker supports it (S14).
* **Decision rules for locks (extracted, Matrix B carries detail):** no mechanism (single writer / natural idempotency); local serialization (single-process critical section suffices); optimistic/conditional mutation (source supports preconditions — *preferred*, removes the stale-holder class entirely); lease (only when HF owns the authority registry *and* the guarded action tolerates rare double-execution = efficiency lock); lease+fencing (HF grants authority AND the acceptance point can check tokens — rare for external APIs); source-native transactional mechanism (always preferred when it expresses the invariant).

### E. Unknown outcome / unknown commit

* Foundational: Two Generals proves a sender can never *know* that its message and its acknowledgement both arrived (S8). 2PC operationalizes this: after a participant votes YES it sits in an **uncertain state** where it can neither commit nor abort unilaterally; coordinator failure blocks participants; "heuristic decisions" forced by operators can contradict the coordinator and corrupt data (S6, S29, S39-context). Gray & Lamport: 2PC blocks "with no process knowing the outcome" (S6).
* API/payments reality: Stripe explicitly caches and replays 500s and tells clients to treat them as **indeterminate** and rely on webhooks for truth (S11). Payment-failover practice: "A missing response is not proof that no charge occurred — query status or wait for the authoritative webhook before another authorization" (S23). Refund-timeout practice: keep the original operation identity, model `submitted_unknown`, never label an ambiguous timeout as rejection "to unblock the flow" (S36).
* Database-client reality: a COMMIT whose reply is lost is outcome-unknown, and honest clients surface a distinct `CommitOutcomeUnknown` error class rather than reporting failure (S37).
* **Hypothesis "absence of success ack ≠ evidence of failure": SUPPORTED** by all of the above. Next-action mapping (retry / reconcile / query / wait / abort / escalate) is derived in Section 9 (Decision Contract) and Rule R3.

### F. Partial failure

* The dual-write problem: database write + broker publish (or any two systems) cannot share a transaction; failure between them silently diverges the systems; the outbox pattern removes one instance of the problem by making the publish a local transaction — but outbox relays are at-least-once, so consumers still need idempotency (S39).
* Durable runtimes make the crash-after-external-effect window explicit: worker executes the external call, crashes before recording the result, runtime re-runs the activity ⇒ duplicate external effect unless the external call was identity-guarded (Temporal docs and tutorials, S16, S33, S34; Azure Durable Functions Q&A: "the code in each activity is idempotent since they may run more than once if the process crashed after the activity started executing but before the result was persisted", S17b; AWS: "if a step fails midway or the invocation is interrupted before the checkpoint lands, the step may run more than once", S18).
* F's required conclusion: "transaction failed" is not one state. Minimum taxonomy of post-operation states for a consequential call: **decided-success, decided-failure (rejected-before-execution), NOT_EXECUTED (known no-effect), UNKNOWN_OUTCOME, EXECUTED_BUT_UNRECORDED (discovered later)** — collapsing these is the root of most incorrect recoveries (F7, F12; S24's pending/submitted_unknown/confirmed model).

### G. Sagas and compensation

* Original model: Garcia-Molina & Salem 1987 — LLTs as T1…Tn with compensating transactions run in reverse on failure; the paper's framing already presumes **semantic** undo defined per transaction, plus forward-recovery variants requiring retryable (idempotent) transactions (S5, S40).
* Production interpretations: Azure Architecture Center: compensation "doesn't always work"; it is application-specific; steps must be idempotent commands; compensation may be worse than offering an alternative path; humans may need to decide (travel-site example) (S20). Conductor/Orkes production notes: "Undo only what completed" (drive from actual task statuses, never assumptions); compensation must itself be idempotent and get *more* retries than the forward path; "Compensation is not rollback — a refund is a new transaction with its own ledger entry"; a saga that cannot undo needs a human (S22). Reactive patterns and Richardson-adjacent material: compensations semantically undo business operations, can't always exist (unsend email), and isolation is absent — intermediate states are visible (S21, S40).
* Compensation against stale assumptions / unknown outcomes: compensating an operation that is in UNKNOWN_OUTCOME risks refunding a charge that never happened or failing to refund one that did — reconcile first (S22's "read the failed execution", S36).
* **H7 SUPPORTED** with strong convergence: compensation is a new domain operation; authorization for it is a business decision (who may refund?), not a technical property.

### H. Event sourcing

* What ES guarantees: append-only stream of domain events as source of truth; rebuild/replay/temporal queries; per-aggregate optimistic concurrency via stream sequence numbers (S25b).
* What ES does **not** guarantee: ES is *not automatically an audit log* — no third-party verifiability, no tamper-evidence by default, event stores compact/scavenge, timestamps are app-clocks (S25); regulatory-grade audit needs chain-of-hash + external timestamp anchoring regardless of ES; ES does not remove the need for idempotent projections/handlers (S25, Anchor Defense piece); CRUD + separate audit table covers "what changed and who did it" for most compliance needs (S25a, S25c decision frameworks).
* Who uses ES and for what: Azure Durable Functions/Durable Task Framework uses event sourcing **internally for orchestrator replay** — i.e., durable execution's history mechanism, not a user-facing mandate (S17). Temporal is event-sourced internally for workflow history (S33). Neither requires the *application* to adopt ES to get durable execution, recovery, receipts, or provenance.
* Simpler alternatives with named scope: (1) current state + append-only audit log; (2) checkpoint + transition journal (this is literally what durable runtimes do for workflow state); (3) immutable receipts per external effect (payments practice, S24); (4) conventional transactional state. Activation conditions for ES: temporal queries ("state as of T"), replays into new projections, event-carried state transfer, complex domain event collaboration. None of these is implied by "HF must be reliable".

### I. Durable workflow systems (semantics only — not a vendor comparison)

| Semantics | Temporal (S16, S33, S34) | Azure Durable Functions (S17) | AWS Step Functions (S38) | AWS Durable Execution SDK (S18) |
| --- | --- | --- | --- | --- |
| Orchestration determinism | Required; replay of event history; workflow code must not do I/O or read wall clock | Required; event-sourced history; no I/O, no `DateTime.Now`, no `Guid.NewGuid()` in orchestrators; violations cause nondeterministic replay | ASL state machine (determinism by construction) | Determinism and replay documented; pass data via step return values |
| Side effects | Only in Activities; workflow `SideEffect()` records result in history and has **no execution guarantee** (may run more than once on decision-task failure) | Only in activity functions; orchestrators "may be replayed multiple times, causing nondeterministic and duplicate I/O" if violated | Tasks via service integrations / activities | Steps; `SideEffect`-class APIs checkpoint results |
| Activity/step execution | At-least-once default; at-most-once configurable (maxAttempts=1) but then "zero times is also possible" | At-least-once; idempotency required by docs and Q&A | Standard: "exactly-once model" for tasks/states *as executed by the service*; Express: at-least-once | At-least-once default; `AtMostOncePerRetry` × no-retry ⇒ "runs exactly once end-to-end" **per attempt semantics, scoped** |
| Duplicate protection guidance | Make activities idempotent; WorkflowID+ActivityID as stable idempotency key; duplicate-rejecting start policies | Design activities idempotent; framework provides replay-safe GUID/time APIs | Unique execution names give idempotent starts (same name+input returns existing execution; different input errors) | Execution names idempotent at start; keys generated *inside* steps for external calls |
| Cancellation/signals/timers | Durable timers, signals, cancellation propagated to activities | Durable timers, external events | Wait-for-callback token pattern | Waits, callbacks |

Extracted reusable semantics (what HF should copy): (1) separate decision logic (deterministic, replay-safe, effect-free) from effect execution (identity-guarded, retryable by policy); (2) replay requires all nondeterminism to be recorded (history) — any external call inside replayed logic is a defect (F10); (3) execution/operation identity must be stable across retries and *derived from logical identity*, not minted per attempt (Temporal's "fresh UUID per retry dedupes nothing", S34; AWS "generate the key inside a step", S18); (4) at-most-once is a valid *policy* for harmful non-idempotent effects but converts duplicates into possible skips — pair with reconciliation.

### J. Source-native guarantees vs harness-owned guarantees

Per-mechanism delegation findings (detail in Section 8, Source-Native Guard Capability Matrix):

| Mechanism | Delegatable to source? | Harness must still own | Cannot be guaranteed generically |
| --- | --- | --- | --- |
| Transaction | Yes, source-local only | Cross-system step ordering, attempt records | Atomicity across ≥2 systems (S39) |
| Conditional write | Yes (source-local invariant) | Choosing the precondition; duplicate-effect guard (version ≠ effect identity) | Fencing arbitrary external APIs without such support |
| Idempotency | Yes, where provider offers keys | Key derivation from *logical* effect; retention beyond provider window | Same-logical-effect-different-payload reconciliation (S11 422/409 semantics conflict with replanning) |
| Version check | Same as conditional write | Nothing (delegate fully) | — |
| Deduplication | Windowed at brokers (S13, S12) | Unbounded durable dedup when harm is material | Window expiration (F11) |
| Authoritative outcome query | Yes | When/how to query; evidence retention | Availability of the query at reconciliation time (F12) |
| Lock | Rarely (resource must enforce) | Nothing for external resources (prefer conditional writes) | Correctness without resource-side enforcement (S1) |
| Approval | Business-level | Recording, enforcement, audit of the approval decision | The approval itself |
| Audit receipt | Source often provides (provider IDs, settlement) | Evidence assembly, tamper-evidence if required | Third-party verifiability by default (S25) |
| Effect identity | Never fully — the *logical* effect is HF's concept | Definition, stability across replanning, persistence | Inferring identity for LLM-generated, re-planned operations (open question OQ-3) |

**H10 assessment:** supported *where native mechanisms exist* (Stripe keys, DynamoDB conditions, HTTP validators): HF-side re-implementation is weaker (no atomicity, window drift, clock skew) and adds failure modes. **Boundary:** (a) not all sources offer native guards; (b) native dedup windows are bounded; (c) native guards do not carry logical-effect identity; (d) harness still owns attempt/evidence records. So the preference is real but not a universal elimination.

---

## 5. CLAIM–EVIDENCE–COUNTEREVIDENCE LEDGER

Status scale: SUPPORTED / PARTIALLY_SUPPORTED / NOT_SUPPORTED / CONTRADICTED / EXPERIMENT_REQUIRED / INSUFFICIENT_EVIDENCE. Confidence: HIGH / MEDIUM / LOW.

| ID | Claim | Evidence Class | Sources | Supporting evidence | Counterevidence | Boundary | Status | Conf. | HF consequence | Falsifier |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C01 | End-to-end exactly-once business effects cannot be guaranteed by a workflow runtime alone; they require target-side idempotency/dedup | FOUNDATIONAL_SYSTEMS_RESULT + VENDOR_DOCUMENTED_SEMANTICS | S8, S14, S15, S34 | Kafka EOS scoped to Kafka loops; Flink: end-to-end EOS needs replayable source + idempotent/transactional sink; Temporal: at-least-once + idempotency = effectively-once | None found in any vendor doc claiming unscoped effect EOS; Step Functions' "exactly-once" is explicitly scoped to workflow execution | Proven only for systems that cannot observe target state | **SUPPORTED** | HIGH | HF contracts must never claim unscoped effect exactly-once | A durable runtime demonstrating exactly-once effects on an arbitrary non-idempotent, non-transactional external API |
| C02 | Absence of a success acknowledgement is not evidence of failure | FOUNDATIONAL_SYSTEMS_RESULT + VENDOR_DOCUMENTED_SEMANTICS | S8, S11, S23, S36, S37 | Two Generals impossibility; Stripe 500-indeterminacy guidance; payment-failover status-check practice; CommitOutcomeUnknown error classes | None against the claim itself; practical counterevidence exists only where effects are read-only/idempotent (ack loss is then harmless to retry) | Holds for consequential effects; for naturally idempotent ops the distinction collapses (safe to retry) | **SUPPORTED** | HIGH | Mandate UNKNOWN_OUTCOME state; forbid timeout=failed mappings | A system able to distinguish message-loss from execution-failure at distance without extra round-trips |
| C03 | Source-native atomic conditional mutation is superior to harness read-check-write for source-local invariants | VENDOR_DOCUMENTED_SEMANTICS + FOUNDATIONAL_SYSTEMS_RESULT | S7a, S9, S30, S31 | RFC 9110 §13; DynamoDB conditional ops atomic; single-statement CAS; lost-update analyses | DynamoDB global tables last-writer-wins breaks optimistic locking (S30); HTTP date validators have 1-second granularity (S9a) — native guards have their own limits | Source-local invariants only; does not dedupe non-idempotent retries by itself | **SUPPORTED** | HIGH | HF Rule R2: prefer native precondition+mutation; ban harness-side read-check-write on guarded resources | A source-local invariant that a harness-side check can enforce more strongly than the source's own conditional write |
| C04 | A distributed lock (incl. consensus-backed) does not protect a resource that does not itself reject stale holders; fencing tokens require resource cooperation | FOUNDATIONAL_SYSTEMS_RESULT + VENDOR_DOCUMENTED_SEMANTICS | S1, S2, S19 | Kleppmann GC-pause/lease-expiry proof; antirez concedes fencing/"avoid the lock" where resources can CAS; Kubernetes leaderelection explicitly no fencing | Antirez: operational clock discipline makes lease-based locks fit for *efficiency* use; HN dissent that fencing pushes the problem into the storage layer | Applies to correctness-class use; efficiency-class locks (dedupe cron work) are out of scope of the claim | **SUPPORTED** | HIGH | HF must not use locks as safety mechanisms for external effects; prefer conditional writes | A lock-only system with demonstrated stale-holder safety against unbounded pauses and no resource-side checks |
| C05 | Compensation is a new business operation, not a technical rollback, and can fail or be impossible | VENDOR_DOCUMENTED_SEMANTICS + ENGINEERING_PRACTICE | S5, S20, S21, S22 | Saga origin (semantic undo); Azure: "compensating transactions don't always work", application-specific; Conductor: refund is new transaction; unsendable email class | SagaLLM-style proposals of LLM-generated compensation exist but are research-grade (arXiv, not production evidence) | Applies where "undo" means semantic business reversal; DB-internal rollbacks are a different mechanism | **SUPPORTED** | HIGH | Compensation modeled as domain ops w/ own identity/authorization/idempotency; never auto-inverse | A generic automatic inverse that is safe across heterogeneous business systems |
| C06 | Event sourcing is neither necessary for durable execution/audit nor sufficient as an audit log | VENDOR_DOCUMENTED_SEMANTICS + ENGINEERING_PRACTICE | S17, S25, S33 | Durable runtimes use internal histories; ES-as-audit-log gaps (verifiability, compaction, app clocks); CRUD+audit-log adequacy analyses | ES advocates: intrinsic complete audit trail & temporal queries within the event store's own trust domain | Claims about *third-party* audit; within one trust domain ES does provide change history | **SUPPORTED** | MEDIUM | ES activation conditions only; default HF state = transactional state + append-only audit/receipts | A compliance regime that accepts vanilla event stores as legally sufficient audit evidence without integrity anchoring |
| C07 | "Exactly-once" vendor claims are boundary-specific and frequently misread | VENDOR_DOCUMENTED_SEMANTICS | S14, S15, S18, S38 | Kafka EOS scope; Flink state-vs-processing wording; AWS "at-most-once applies per attempt, not per workflow"; Step Functions exactly-once *execution model* vs external task processing | None — even vendors scope their own claims; confusion is in secondary literature | Applies to claims as documented by vendors | **SUPPORTED** | HIGH | HF glossary fixes delivery/processing/effect suffixes; bans unscoped usage | A vendor doc claiming unscoped end-to-end effect exactly-once |
| C08 | Stable effect identity is required only for a subset of effects (harmful non-idempotent class), not every tool invocation | DESIGN_RECOMMENDATION (from evidence) | S9, S11, S18, S34, S13 | RFC 9110: idempotent methods safe to retry w/o keys; AWS SDK distinguishes at-least-once (idempotent) vs at-most-once (payment) steps; Temporal keys only where needed | Cost of keys is low, so some practitioners apply them universally (engineering folklore); universal dedup stores exist | Read-only and naturally idempotent effects demonstrably need none; "universal" remains *possible*, not *necessary* | **SUPPORTED** (necessity claim); universal application = `NOT_SUPPORTED` as a requirement | MEDIUM | Effect-class-driven identity requirement (Matrix A) | A scenario where a read-only effect requires identity for correctness (not for analytics) |
| C09 | Delayed duplicates beyond native dedup windows occur and are material for harmful effects | VENDOR_DOCUMENTED_SEMANTICS + ENGINEERING_PRACTICE | S11, S13 | SQS 5-min window expiry → treated as new message; Stripe 24h pruning; visibility-timeout redeliveries | None found claiming windows cover all duplicate horizons | Windows differ per system; horizon = business-defined duplicate-sensitivity period | **SUPPORTED** | HIGH | HF dedup horizon = business-defined, must exceed native windows where harm is material | A native provider guaranteeing unbounded dedup retention |
| C10 | Durable runtimes re-execute activities/steps after crash-before-record; therefore external calls need identity guards | VENDOR_DOCUMENTED_SEMANTICS | S16, S17b, S18, S35 | All four runtimes document at-least-once step semantics; crash-window analyses | None; at-most-once modes exist but trade skips for duplicates (S18) | At-most-once + no-retry narrows but "per attempt, not per workflow" (S18) | **SUPPORTED** | HIGH | HF effect executor: identity-before-attempt ordering; receipts after | A runtime that checkpoints *before* external calls and never replays them (would still not survive lost acks — C02) |
| C11 | Orchestrator/replay code containing direct external effects is a correctness defect | VENDOR_DOCUMENTED_SEMANTICS | S16, S17, S18 | Azure: orchestrator I/O causes "nondeterministic and duplicate I/O"; Temporal workflow determinism constraints; AWS determinism docs | None | Applies to replay-based runtimes; non-replaying engines differ | **SUPPORTED** | HIGH | HF separates plan/decide (pure) from act (guarded); replayed logic contains zero external calls | A replay-based engine that safely tolerates nondeterministic external calls in replayed logic |
| C12 | Leases require clock/rate assumptions and admit dual holders during skew; fencing closes it only at token-checking resources | FOUNDATIONAL_SYSTEMS_RESULT + VENDOR_DOCUMENTED_SEMANTICS | S1, S3, S19 | Kubernetes skew-rate tolerance config; Gray & Cheriton lease semantics; Kleppmann analysis | Antirez: practically bounded clocks suffice for efficiency purposes | Correctness-class assessment | **SUPPORTED** | HIGH | HF lease usage restricted to HF-internal authority; fencing only where an acceptance point can check tokens | A lease protocol with proven no-dual-holder property under arbitrary clock skew without resource checks |
| C13 | Native dedup windows + fingerprints conflict with legitimate re-planning (same logical effect, changed payload) | ENGINEERING_PRACTICE (from S11/S36/S41 semantics) | S10, S11, S36 | 422/409 fingerprint-conflict semantics; "unknown provider outcome is not a new operation" identity rules | Stripe recommends fresh keys when *modifying* a request — implying new logical effect; boundary between correction and new effect is a business call | Depends on HF's definition of logical-effect identity under replanning | **PARTIALLY_SUPPORTED** | MEDIUM | HF must define identity stability rules for re-planned operations (open question OQ-3) | A general rule that always classifies payload changes as same-effect vs new-effect without business input |
| C14 | HF-owned distributed-systems machinery can *reduce* reliability when the source has stronger native guarantees | DESIGN_RECOMMENDATION (synthesis) | S1, S2, S14, S30, S39 | Weaker harness checks (non-atomic read-check-write, harness locks, window-limited dedup) fail where native atomic guards succeed; Redlock critique; dual-write problem | Cases with no native guard where harness machinery is the *only* protection; harness records still needed for evidence | Preference, not elimination; holds only where native mechanism provably expresses the invariant | **SUPPORTED** as preference with named boundary | MEDIUM | Source-native gate in HF promotion process (anti-sycophancy for prior HF ledger plans) | A class of invariant where a harness-side mechanism beats every native option |
| C15 | 2PC-class distributed transactions are a poor fit as an HF coordination mechanism (blocking; heuristic decisions corrupt) | FOUNDATIONAL_SYSTEMS_RESULT | S6, S29, S39 | Blocking-on-uncertain proof; XA heuristic-commit hazards; industry retreat to sagas/outbox | XA remains viable in closed single-organization database fleets | Heterogeneous external APIs (HF's reality) cannot participate in 2PC at all | **SUPPORTED** for HF scope | HIGH | Do not design HF around distributed transactions; design for local atomicity + compensation/reconciliation | Wide adoption of XA-style coordination across arbitrary SaaS APIs |
| C16 | Pub/Sub "exactly-once delivery" = no-redelivery-after-ack, not exactly-once processing | VENDOR_DOCUMENTED_SEMANTICS | S12 | Docs scope guarantee to acknowledgments & redelivery; pull-only; region-scoped | — | Delivery-layer guarantee only | **SUPPORTED** | HIGH | Terminology table entry; do not infer processing guarantees | Google documentation extending the guarantee to downstream processing |
| C17 | SQS FIFO dedup ≠ consumer idempotency (dedup is send-side, windowed) | VENDOR_DOCUMENTED_SEMANTICS + ENGINEERING_PRACTICE | S13 | Redelivery after visibility timeout bypasses dedup window; analyses of the trap | None | FIFO queues | **SUPPORTED** | HIGH | Effect-level dedup cannot be inherited from queue dedup | AWS documentation guaranteeing consumer-side dedup via MessageDeduplicationId |
| C18 | AWS Step Functions Standard Workflows' "exactly-once execution model" refers to workflow/task *starts by the service*, and coexists with retry-driven re-execution; Express is at-least-once | VENDOR_DOCUMENTED_SEMANTICS | S38 | AWS docs' own scoping and the Standard-vs-Express table; idempotent same-name start behavior | None (vendor self-consistent); secondary sources sometimes over-read it | Scoped to Step Functions execution semantics; downstream Lambda task processing has its own retry semantics | **SUPPORTED** | HIGH | Evidence for C07 terminology gate | Vendor doc unifying execution-model and external-effect guarantees |
| C19 | HF can rely on provider webhooks as sole truth for outcome resolution | ENGINEERING_PRACTICE (negation tested) | S11, S23, S36 | Practice recommends webhooks as *part* of resolution; webhook delivery itself is at-least-once, unordered, and can be missed (orphan-recovery jobs recommended, S36-adjacent practice) | — | Webhooks are evidence inputs, never sole authority | **CONTRADICTED** (as stated) | HIGH | Reconciliation = query + webhook + receipts, with polling fallback | A provider guaranteeing transactional, ordered, lossless webhook delivery |
| C20 | Checkpoint+journal (durable-runtime style history) is sufficient internal state machinery for HF workflow durability; full ES adds capabilities only under named activation conditions | ENGINEERING_PRACTICE + VENDOR_DOCUMENTED_SEMANTICS | S15, S16, S17, S25 | Flink/Temporal/Azure implement state via checkpoints + journals/histories; ES-specific capabilities enumerated separately | ES value in domains with temporal-query requirements (federal audit analysis, S25d) | HF-internal state vs. business-domain event streams | **SUPPORTED** for HF-internal state | MEDIUM | Default HF state model: transactional state + append-only journal/receipts | An HF requirement that can only be met with temporal state reconstruction |

### Core hypotheses H1–H10 — verdicts

| # | Hypothesis | Verdict | Core evidence | Counterevidence / boundary | Failure case if ignored | Confidence | HF consequence | Falsifier |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| H1 | Durable workflow execution ≠ exactly-once external effects | **SUPPORTED** | C01, C10, C11 | At-most-once policies trade duplicates for skips | Double-charge after crash-before-record | HIGH | Effect contracts independent of runtime durability claims | Demonstrated effect exactly-once from runtime durability alone |
| H2 | Native atomic conditional mutation preferred for source-local invariants | **SUPPORTED** | C03 | Global-table LWW caveat; validator granularity; doesn't dedupe retries | Lost updates via harness read-check-write | HIGH | R2 rule; capability discovery per source | Harness check provably stronger than native guard for a source-local invariant |
| H3 | Unknown outcome must be explicit | **SUPPORTED** | C02, S6, S11, S36, S37 | Read-only effects don't need the state | Timeout treated as failure → duplicate charge or wrongful abort | HIGH | UNKNOWN_OUTCOME in every consequential-effect state machine | A method that always resolves outcome at first failure detection with zero ambiguity |
| H4 | Blind retry unsafe when outcome unknown AND duplicates harmful | **SUPPORTED** | C02, C09, S13, S23 | Retry *with* stable identity or native key is the safe form; naturally idempotent effects exempt | Duplicate payment on retry-after-timeout | HIGH | Retry gate: retryability decided per effect class, not per error | Idempotent-by-construction effect harmed by retry |
| H5 | Effect identity needed only for selected classes | **SUPPORTED** | C08 | Universal keying is harmless but not necessary; keys can mislead when identity is wrong (C13) | Ledger bloat + false dedup on reads; missing identity on payments | MEDIUM | Matrix A identity column | Read-only effect requiring identity for correctness |
| H6 | Lock without fencing may fail vs stale writers | **SUPPORTED** | C04, C12 | Efficiency-class locks excluded | Zombie worker overwrites after ownership transfer | HIGH | R5 rule; no harness locks for external correctness | Lock-only system safe under unbounded pauses w/o resource checks |
| H7 | Compensation = separate domain operation | **SUPPORTED** | C05 | DB rollbacks are a different (in-system) mechanism | Auto-refund against unknown outcome; unsendable-email inverse | HIGH | Compensation contract: identity, authorization, idempotency, ordering | Generic safe auto-inverse across business systems |
| H8 | Event sourcing not required for every durable/auditable harness | **SUPPORTED** | C06, C20 | ES valuable under temporal-query/rebuild activation conditions | Mandatory ES adds schema/versioning burden w/o named failure prevented | MEDIUM | ES activation conditions; default simpler state model | HF requirement class only satisfiable via ES |
| H9 | Exactly-once terminology overloaded; decompose by boundary | **SUPPORTED** | C01, C07, C16, C17, C18 | — | HF promises it cannot keep; consumers over-trust | HIGH | Glossary + terminology ban | Vendor/standard defining unscoped end-to-end effect exactly-once |
| H10 | More harness machinery can reduce reliability vs native guarantees | **SUPPORTED (as preference)** | C14 | Holds only where native mechanism expresses the same invariant more strongly; harness evidence records remain necessary | Harness dedup window < provider's atomic dedup; harness lock weaker than native CAS | MEDIUM | Source-native gate; capability matrix as input to design | Invariant where harness-side implementation dominates all native options |

---
## 6. DISTRIBUTED SYSTEMS FAILURE TAXONOMY v0.1 (proposed for HF)

Evidence supports **orthogonal dimensions**, not a single tree. Proposed axes:

* **D1 Outcome determinacy** — is the effect's outcome known?
* **D2 Multiplicity** — how many times did the logical effect occur (0/1/≥2/unknown)?
* **D3 Freshness** — was the state the decision was based on current at mutation time?
* **D4 Authority** — was the writer entitled *at execution time* (ownership/lease/fencing)?
* **D5 Scope** — how many systems does the deviation span (1 source / multi-system)?
* **D6 Recoverability** — can the deviation be corrected by machine (retry/reconcile/compensate) or only by humans?

### Failure classes (IDs proposed for HF)

| ID | Class | Definition (observable) | Axes | Scenario refs |
| --- | --- | --- | --- | --- |
| FC-01 | **Outcome ambiguity** | A consequential operation terminated without a usable result signal (timeout, connection loss, indeterminate 5xx, lost ack) | D1=unknown | F1, F12 |
| FC-02 | **Lost acknowledgement** | Effect may have executed; ack/response provably or possibly lost | D1=unknown | F1 |
| FC-03 | **Duplicate effect** | Logical effect executed ≥2 times (identical or near-identical outcome) | D2≥2 | F2, F3, F11 |
| FC-04 | **Delayed duplicate** | Duplicate beyond the dedup/idempotency window | D2≥2, late | F11 |
| FC-05 | **Stale-state mutation** | Mutation applied on state that changed after the read (lost update) | D3=stale | F4 |
| FC-06 | **Write conflict** | Two legitimate writers produce conflicting outcomes; neither is "wrong" individually | D3+D5 | F5 |
| FC-07 | **Lease loss** | Worker's authority expired mid-flight (it may or may not know) | D4 | F6 |
| FC-08 | **Stale writer / zombie** | Worker acts after authority moved to another worker | D4 | F6 |
| FC-09 | **Partial multi-system effect** | A subset of a multi-system operation committed | D5>1 | F7 |
| FC-10 | **Crash-after-effect / unrecorded effect** | External effect committed; local/recorded state does not reflect it | D1(local)=unknown, D5=2 | F3, F7 |
| FC-11 | **Compensation failure** | Compensating operation itself fails or is unsafe to run | D6 | F8 |
| FC-12 | **Irreversibility** | Effect has no meaningful inverse; deviation permanent without new forward operations | D6 | F9 |
| FC-13 | **Compensation of unknown outcome** | Compensation attempted while original outcome unknown (compensate-nothing / double-compensate) | D1+D6 | F8, F12 |
| FC-14 | **Reconciliation failure** | Authoritative query unavailable, ambiguous, or conflicting evidence | D1+D6 | F12 |
| FC-15 | **Replay-induced duplication** | Replayed control logic re-issues an external effect | D2 | F10 |

Not forced into one hierarchy: D1–D6 are independent; a single incident maps to a *set* of classes (e.g., F6 = FC-07 + FC-08 + possibly FC-03).

---

## 7. REQUIRED FAILURE SCENARIOS F1–F12

Each scenario: **observable facts / unsafe assumption / minimum protection / stronger optional protection / residual uncertainty / recovery route.**

### F1 — Lost acknowledgement
* **Observable facts:** request sent; remote may have executed; no response (timeout/reset). Nothing on the wire distinguishes "lost before execution" from "lost after commit" (S8).
* **Unsafe assumption:** timeout ⇒ failure ⇒ safe to retry or abort.
* **Minimum protection:** classify effect (Matrix A); if harmful-if-duplicated, mark operation `UNKNOWN_OUTCOME` and stop automatic retry.
* **Stronger:** native idempotency key held stable across retries (S11) → retry is safe; plus authoritative status query before any compensating action (S23).
* **Residual uncertainty:** status API may lag the write; window between execution and visibility.
* **Recovery route:** reconcile (query/webhook/settlement) → decided state; escalate if evidence conflicts.

### F2 — Duplicate delivery
* **Observable facts:** same logical operation arrives twice (broker redelivery, user double-submit, retry storm).
* **Unsafe assumption:** dedup at one layer (queue window, HTTP method semantics) implies effect-level dedup (S13, C17).
* **Minimum protection:** for naturally idempotent effects, nothing needed beyond verification; else stable logical-effect identity checked in a durable store before attempt.
* **Stronger:** source-native idempotency key + HF-side durable dedup keyed on logical identity (both layers).
* **Residual uncertainty:** identity inference for semantically-equal-but-payload-different duplicates (C13).
* **Recovery route:** if duplicate effect detected after the fact → reconcile against source truth; compensate only if reversible and authorized (FC-03).

### F3 — Retry after crash (crash after external success, before recording completion)
* **Observable facts:** runtime shows attempt incomplete; provider shows (or may later show) success. Documented window in Temporal/Azure/AWS semantics (S16, S17b, S18; S35).
* **Unsafe assumption:** incomplete-in-runtime ⇒ not executed externally.
* **Minimum protection:** at-most-once policy for harmful effects (no auto-retry) + UNKNOWN_OUTCOME (S18 semantics).
* **Stronger:** identity generated *inside* a checkpointed step / derived from workflow+activity ID (S16, S18) so post-crash retries dedupe at the source; receipt recorded before returning success.
* **Residual uncertainty:** provider key retention window (F11 interplay).
* **Recovery route:** reconcile by effect identity; adopt executed outcome into local state rather than re-executing.

### F4 — Stale read
* **Observable facts:** read value V at t0; write at t1>t0; value changed in between by another writer.
* **Unsafe assumption:** read-check-write proves anything about t1 state (S31).
* **Minimum protection:** source-native conditional mutation (expected version / ETag / condition) → 412/ConditionalCheckFailed ⇒ re-read, re-decide (S9, S30).
* **Stronger:** transaction spanning invariant at the source; or domain-level monotonic preconditions (`status='unpaid'`) making stale writes *fail* rather than overwrite.
* **Residual uncertainty:** none for source-local invariant when native guard used; cross-system invariants remain unprotected (C03 boundary).
* **Recovery route:** on precondition failure → refresh → revalidate business assumptions → retry or abort; never force-write.

### F5 — Concurrent writers
* **Observable facts:** two legitimate workers submit conflicting mutations near-simultaneously.
* **Unsafe assumption:** "first wins" or "last wins" is acceptable; or that a harness lock made them serial.
* **Minimum protection:** source-native serialization point (conditional write / transaction / queue-per-key).
* **Stronger:** business-level concurrency control — versions, epochs, status preconditions; approval for the conflicting class.
* **Residual uncertainty:** winner legitimacy is a business question, not a technical one.
* **Recovery route:** loser reconciles its assumptions against the winner's outcome; compensate its own partial work if authorized.

### F6 — Lease expiration (A holds execution, lease expires, B takes over)
* **Observable facts:** A's lease expired (possibly unnoticed by A); B active; both may issue effects (S1; Kubernetes no-fencing admission S19).
* **Unsafe assumption:** lease expiry ⇒ old holder will stop; new holder is sole writer.
* **Minimum protection:** treat post-expiry actions by A as FC-08 risks: A must stop on expiry notice *and* B's writes must be conditional on source state (epoch/version), making stale writes fail at the source.
* **Stronger:** fencing/epoch tokens checked at an acceptance point (only where the resource supports checks, S1); else transfer protocol with drain + conditional-write gatekeeping.
* **Residual uncertainty:** window between expiry and A's noticing is irreducible (S1) — protection must be at the resource, not in A.
* **Recovery route:** B reconciles in-flight operations of A via effect identity registry before proceeding.

### F7 — Partial multi-system effect (A succeeds, B fails)
* **Observable facts:** system A state changed; system B did not; no shared transaction (S39).
* **Unsafe assumption:** single "transaction failed" status suffices; or that re-running the whole step is safe for A.
* **Minimum protection:** per-system outcome records (receipts), explicit sub-state per system (decided-success / NOT_EXECUTED / UNKNOWN per F's taxonomy).
* **Stronger:** step ordering with pivot-last; compensable-step registry; or restructure so B's invariant is enforceable before A's irreversible step.
* **Residual uncertainty:** A's effect may itself be unknown if A's ack was lost (compound FC-01+FC-09).
* **Recovery route:** forward-recover B (retry with identity) or compensate A (domain op, authorized) — decided by effect classes, never blanket.

### F8 — Compensation failure
* **Observable facts:** compensating op (refund/release/cancel) failed or is stuck.
* **Unsafe assumption:** compensation is more reliable than the forward path; failure of compensation can be retried forever harmlessly (it cannot — compensation is a consequential effect too, S22).
* **Minimum protection:** compensation treated as effect with own identity, idempotency, retry budget; failure raises an alert state (FC-11), never silent.
* **Stronger:** compensation gets longer retry horizon than forward path (S22); dedicated escalation queue; human authorization for manual correction paths.
* **Residual uncertainty:** compensation may itself be stuck in UNKNOWN_OUTCOME — same machinery applies recursively.
* **Recovery route:** escalate to human/ops with full evidence bundle (S20, S22).

### F9 — Irreversible effect
* **Observable facts:** effect has no meaningful inverse (email sent, goods shipped, legal filing, notification published).
* **Unsafe assumption:** a saga/rollback framework can undo it; or that "compensate: true" exists for every tool.
* **Minimum protection:** effect class marked `NON_IDEMPOTENT_IRREVERSIBLE`; approval gate before execution; no compensation field in its contract.
* **Stronger:** pivot-last ordering (all fallible, reversible steps complete first — S21/S40 practice); dry-run/preview modes; staged commitments.
* **Residual uncertainty:** none removed — only exposure reduced.
* **Recovery route:** forward correction as a *new* business operation (apology email, new shipment) — an explicitly authorized domain decision, not "undo".

### F10 — Replay containing unsafe external side effect
* **Observable facts:** durable runtime replays orchestration history; replayed logic performs I/O or non-recorded nondeterminism → duplicate I/O (S17: "causing nondeterministic and duplicate I/O with external systems").
* **Unsafe assumption:** workflow durability makes replayed side effects safe (H1/H2 interplay, C11).
* **Minimum protection:** external calls only in activity/step boundaries (non-replayed), deterministic APIs inside replayed logic (S16, S17, S18).
* **Stronger:** recorded nondeterminism (`SideEffect`-class APIs) with knowledge that those APIs still have *no exactly-once execution guarantee* (S16 SideEffect docs) — i.e., even recorded side effects must be identity-safe.
* **Residual uncertainty:** none for well-formed replays; history corruption is a separate disaster class.
* **Recovery route:** runtime-level; HF's duty is the constraint, not the replay engine.

### F11 — Delayed duplicate (beyond retry/idempotency window)
* **Observable facts:** duplicate arrives after provider pruned the key (Stripe 24h, S11) or after queue window (SQS 5 min, S13) or after execution-name retention (90 days, S38).
* **Unsafe assumption:** "the dedup window expired ⇒ the operation is finished and safe to re-run."
* **Minimum protection:** HF durable dedup keyed by logical effect with retention ≥ business duplicate-sensitivity horizon; monotonic source-side preconditions (`status` transitions) that make late duplicates *fail* rather than re-apply (C03 note).
* **Stronger:** unbounded (or long-retention) effect-identity store for material effects; provider-side dedup where retention is contractual.
* **Residual uncertainty:** storage lifetime vs. business horizon; GDPR/retention conflicts (OQ-5).
* **Recovery route:** duplicate detected late → reconcile + compensate if authorized (FC-04/FC-03).

### F12 — Unknown authoritative state (no immediate status API)
* **Observable facts:** consequential op issued; outcome unknown; no status endpoint (or it's down); webhooks absent/missed.
* **Unsafe assumption:** "after T minutes with no evidence, treat as failed."
* **Minimum protection:** explicit `UNKNOWN_OUTCOME` persisted with full attempt evidence; *no* automatic retry or compensation.
* **Stronger:** multi-source reconciliation (status API, webhook, settlement/report, human contact), each with own freshness/authority model (S23, S24, S36); deadline-based escalation.
* **Residual uncertainty:** may persist indefinitely (reconciliation failure FC-14) — a permanent, visible limbo with an owner is the correct end state, not a synthetic decision.
* **Recovery route:** scheduled reconciliation with backoff; escalation with evidence; customer/business-process workaround decided by humans (S20's travel example).

---

## 8. REQUIRED COMPARISON MATRICES

### Matrix A — Effect class (proposed v0.1, not final HF enums)

| Effect class | Retry policy | Identity requirement | Reconciliation requirement | Validation requirement | Authorization sensitivity | Compensation possibility |
| --- | --- | --- | --- | --- | --- | --- |
| **READ_ONLY** | Free retry; stale-tolerance policy | None (request id for tracing only) | None (freshness/validation at use site) | Validate freshness if used for consequential decisions (E-tag/If-None-Match optional) | Low (authn only) | N/A |
| **IDEMPOTENT_WRITE** (put/upsert/set-state where reapplication is a no-op) | Auto-retry with backoff; safe by construction | Request identity for tracing; effect identity not required *if* application-on-repeated-key is verified | On contradiction only | Verify true idempotency (idempotent *syntax* ≠ idempotent *effect*, e.g., PUT to a counter) | Low–medium | Rarely needed (re-apply forward) |
| **GUARDED_WRITE** (native precondition/key exists: conditional write, idempotency key) | Auto-retry **with the same stable key/precondition** | REQUIRED: stable logical identity mapped onto native key/precondition | Status query on unknown outcome; duplicate-proofness delegated to source within its window | Verify native window ≥ duplicate horizon; else add HF dedup | Medium | Domain op if business-reversible |
| **NON_IDEMPOTENT_REVERSIBLE** (charge, booking) | At-most-once by default; retry only under identity guard or after reconcile | REQUIRED: logical effect identity + durable dedup | REQUIRED on any unknown outcome | Provider receipt verification | High | Yes — as separate authorized domain op |
| **NON_IDEMPOTENT_IRREVERSIBLE** (send, publish, ship, file) | At-most-once; NO auto-retry; reconcile-then-escalate | REQUIRED | REQUIRED (evidence-first) | Pre-execution validation + approval gate | Highest (explicit approval) | **None** — forward correction ops only |

Do-not-assume note retained: these are evidence-derived starting classes; HF may subdivide (e.g., "guarded & reversible") after fault-injection data.

### Matrix B — Concurrency mechanism

| Mechanism | Protected invariant | Assumptions | Failure mode | Complexity | Source support required | Cross-system applicability | Stale-worker resistance |
| --- | --- | --- | --- | --- | --- | --- | --- |
| No special mechanism | "Duplicate/stale writes are harmless" | Natural idempotency or single writer | Silent lost updates if assumption wrong | None | None | Yes (trivially) | None |
| Serialization (HF-local, single-writer queue) | One worker at a time per HF | HF is sole writer; process survives | HF restart loses serialization; multiple HF instances break it | Low | None | No | Poor (vs. multi-instance) |
| Optimistic concurrency (harness-side version bookkeeping) | HF's *view* consistency | HF state is authoritative | Diverges from source; race vs. external writers | Medium | None | No | Poor |
| **Source-native conditional mutation** | Source-local invariant | Source supports preconditions; no multi-object invariants | Precondition too weak (e.g., version≠effect-dedup) | Low | **Yes (native)** | Per-source only | **Strong** (rejected at source) |
| Transaction | Atomic multi-object invariant *in one system* | Same-system scope | Blocks; doesn't span systems | Medium | Native | No (S39) | Strong within system |
| Lock (harness or DLM) | Mutual exclusion *advice* | Time bounds hold; holder honest | GC pause/delay ⇒ dual holders; no resource enforcement | Med–high | Resource must enforce to be safe | No (resource-bound) | **None without fencing** (S1, S19) |
| Lease | Time-bounded authority | Clock skew bounded; expiry noticed | Dual holders in skew window | Medium | Registry (HF or k8s-class) | No | Weak alone (S19) |
| Lease + fencing | Authority + resource-rejected stale writes | Resource can check monotonic tokens | Requires monotonic token source (consensus-class) | High | Resource-side token check | No | **Strong** where enforced |
| (Derived rule) **Source-native transactional mechanism** | The business invariant itself | Source exposes it (status preconditions, conditional writes) | Mis-specified precondition | Low–medium | Native | Per-source | Strong |

Evidence boundary: no mechanism in this table protects a *cross-system* invariant; that class requires saga-style compensation or restructured invariants (S5, S39).

### Matrix C — Recovery strategies mapped to observable failure states

| Recovery strategy | Applicable observable state | Preconditions | Failure mode of the recovery itself | Evidence |
| --- | --- | --- | --- | --- |
| Retry (identity-guarded) | Decided-failure at transport layer; or guarded unknown | Stable effect identity / native key; transient error class | Duplicate if identity lost; retry storm | S11, S18, S34 |
| Retry (unguarded) | Naturally idempotent effects only | Verified idempotency | Duplicate effect if idempotency misjudged | S9 |
| Reconcile (query authoritative state) | UNKNOWN_OUTCOME | Status API/webhook exists & is authoritative | Query lag; unavailable API (FC-14) | S23, S36 |
| Re-read (refresh state) | Stale-read rejection (412/cond-fail) | Source readable | Racing writers loop (need backoff/bound) | S9, S30 |
| Rebind/revalidate | Business assumptions expired (price/stock/approval) | Revalidation logic exists | Decision changes mid-flow (must re-authorize) | S20 |
| Forward recovery | Failed step before pivot; retryable steps | Idempotent/identity-guarded steps | Same as retry | S5, S40 |
| Compensate | Decided-success partial effects, authorized | Domain-defined inverse op; pivot not yet passed | Compensation failure (FC-11); compensating unknown outcomes (FC-13) | S20, S22 |
| Human escalation | Everything ambiguous/material | Escalation path, evidence bundle | Human latency; manual error | S20, S22 |
| Abort (decide NOT done) | Pre-execution failure classes only | Proof of non-execution (e.g., rejected-before-send) | Wrong abort on unknown (FC-01 misuse) | S37 distinction |

---
## 9. EFFECT / RETRY / RECONCILIATION DECISION CONTRACT v0.1 (machine-addressable)

Field status: REQUIRED / CONDITIONAL / EXPERIMENTAL / REJECTED. Fields not supported by evidence are not included.

```yaml
EffectContract:
  effect_class:            REQUIRED        # enum per Matrix A
  logical_effect_identity: REQUIRED        # stable id; for READ_ONLY may be null
  operation_identity:      REQUIRED        # groups attempts; distinct from effect identity
  duplicate_harm:          REQUIRED        # NONE | RECOVERABLE | MATERIAL
  unknown_outcome_policy:  REQUIRED        # MUST be one of: RECONCILE_FIRST | IDENTITY_GUARDED_RETRY | NO_RETRY_ESCALATE
  retry_policy:            REQUIRED        # derived from effect_class + identity; never free-text
  receipt_policy:          REQUIRED        # record attempt + response evidence + provider refs

  source_idempotency_capability:   CONDITIONAL   # none | key + window | dedup window | unknown
  source_conditional_write:        CONDITIONAL   # bool + mechanism (etag/version/condition)
  source_status_query:             CONDITIONAL   # bool + authority/freshness model
  source_dedup_window:             CONDITIONAL   # duration or null (null => unbounded duplicates possible)
  retention_horizon:               CONDITIONAL   # REQUIRED_IF duplicate_harm=MATERIAL; >= business duplicate-sensitivity period

  reversibility:                   CONDITIONAL   # REQUIRED_IF multi-step flow member: REVERSIBLE | PIVOT | IRREVERSIBLE
  compensation_support:            CONDITIONAL   # REQUIRED_IF reversibility=REVERSIBLE: named domain op + authorization + own identity
  authorization_sensitivity:       CONDITIONAL   # REQUIRED_IF class in {NON_IDEMPOTENT_*} or privileged source

  # EXPERIMENTAL (not promoted):
  semantic_undo_inference:         EXPERIMENTAL
  auto_cross_system_reconciliation: EXPERIMENTAL
  # REJECTED (evidence contradicts):
  exactly_once_effect_flag:        REJECTED      # C01
  harness_lock_for_external_correctness: REJECTED # C04
  ledger_for_every_tool_call:      REJECTED      # C08 (reads/natural idempotency need none)
  timeout_equals_failure:          REJECTED      # C02
```

**Derived decision procedure (normative sketch):**

1. Classify effect → set retry/identity/reconciliation defaults from Matrix A.
2. If `duplicate_harm = MATERIAL` → identity REQUIRED; prefer native key (map logical identity → native key); if native window < retention horizon → enable HF durable dedup.
3. On failure signal → classify: *rejected-before-execution* (4xx with proof), *unknown* (timeout/5xx/lost ack per C02) — map 5xx to UNKNOWN unless the source documents otherwise (Stripe's 500 semantics show even 5xx may have executed, S11).
4. UNKNOWN_OUTCOME → next action order: (a) query authoritative status; (b) wait for webhook within deadline; (c) identity-guarded retry only if native key held; (d) escalate. Never compensate from UNKNOWN (FC-13).
5. Record receipts at every transition; ack ≠ outcome (C02).

---

## 10. SOURCE-NATIVE GUARD CAPABILITY MATRIX

Goal: which invariant classes can be *delegated* to authoritative sources (not a vendor comparison).

| System | Conditional writes | Versions/preconditions | Transactions | Idempotency keys | Dedup | Status reconciliation | Leases | Fencing |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **Stripe-class payment APIs** (S11) | n/a (POST semantics) | — | — | **Yes** (Idempotency-Key, ≥24h, parameter-conflict error, 500-replay+indeterminacy guidance) | — | Webhooks + retrieve APIs (recommended resolution path) | — | — |
| **HTTP/REST resources** (RFC 9110, S9) | **Yes** (If-Match / If-Unmodified-Since / If-None-Match, 412) | ETag / Last-Modified validators | — | Proposed draft only (expired, S10) | — | GET revalidation | — | — |
| **PostgreSQL-class RDBMS** (S31) | Yes (WHERE/CAS; `attribute`-style) | Row versions; SELECT FOR UPDATE | **Yes** (local ACID) | Via unique constraints + ON CONFLICT | Unique constraints | SELECT | Advisory locks (session-scoped) | Row-level CAS effectively fences |
| **DynamoDB** (S30) | **Yes** (condition expressions, atomic; zero capacity on failed condition) | Version attributes / optimistic locking | TransactWrite* items | Client-minted keys via conditional put | Conditional put as dedup | Consistent reads | — | Conditional put with monotonic attr can act as fencing |
| **MongoDB** (S31b) | Yes (filter as precondition, findOneAndModify) | Document version pattern | Multi-doc (replica-set scoped) | Unique index + upsert | Unique index | Reads | — | — |
| **Kafka** (S14) | n/a | Producer ID + sequence (per-partition dedup) | Transactions (Kafka-internal read-process-write) | Transactional.id dedup of zombie producers | PID+seq (broker-enforced) | Read_committed / offsets | transactional.id epochs | **Yes, broker-enforced** (`ProducerFencedException`) |
| **SQS FIFO** (S13) | — | — | — | MessageDeduplicationId | **5-min window, send-side only** | VisibilityTimeout redelivery | — | — |
| **Google Pub/Sub** (S12) | — | — | — | — | Redelivery suppression after ack (region-scoped, pull-only exactly-once mode) | Ack-with-result API | — | Latest-ack-id rule |
| **Temporal** (S16, S34) | — | Workflow ID reuse policies | Event-history transactions (internal) | WF-ID+Activity-ID recommended key; duplicate-reject start policies | Start/dedup policies | Activity results from history | Task queue assignment | Workflow-task fencing internal |
| **Azure Durable Functions** (S17) | — | Orchestration instance uniqueness | Internal event-sourced history | Instance id semantics | Instance dedup | Orchestration status queries | — | Internal |
| **AWS Step Functions** (S38) | — | Execution-name uniqueness (90d) | Internal | Same-name same-input → idempotent start | Execution names | Execution history + DescribeExecution | — | Internal |
| **AWS Durable Execution SDK** (S18) | — | Execution names | Checkpoint log | Keys minted inside steps | Checkpointed step results | Replay/checkpoint reads | — | Internal |
| **Kubernetes Lease / client-go** (S19) | Optimistic concurrency on objects (resourceVersion) | resourceVersion | — | — | — | Watch/Get | **Lease API** | **Explicitly NOT provided** ("a.k.a. fencing") |
| **ZooKeeper / etcd** (S1, S14-context) | CAS on znodes / revisions | zxid / ModRevision | Multi-op txn (limited) | — | — | Reads | Ephemeral + TTL leases | **Yes** (zxid/revision as fencing token) |

**Delegation conclusions (evidence-bound):**

1. *State-invariant class* → delegate to conditional writes/transactions at the source (R2).
2. *Duplicate-effect class within native window* → delegate to provider idempotency keys / broker dedup — with the window recorded in the EffectContract.
3. *Duplicate-effect class beyond window or where no native key exists* → harness-owned durable dedup (identity + retention ≥ horizon).
4. *Authority/stale-writer class* → only fence-capable resources (ZooKeeper/etcd-class, brokers with epochs) can enforce; arbitrary SaaS APIs cannot ⇒ design around conditional state transitions instead of locks.
5. *Outcome-evidence class* → status APIs/webhooks are the authority; harness stores receipts, not truth.

---

## 11. ARCHITECTURE DECISION RULES (testable; for HF engineering review)

Format: `IF <condition> THEN <mechanism> BECAUSE <evidence> UNLESS <boundary>` with required sub-fields.

**R1 — Native key adoption.**
IF a consequential source offers caller-supplied idempotency keys THEN map HF logical-effect identity onto that key BECAUSE vendor-documented dedup + replay semantics are atomic at the source (S11, S10) UNLESS the native retention window is shorter than the business duplicate horizon (then add HF dedup too, R6).
*Invariant:* one logical effect ≤ one execution. *Failure prevented:* F1/F3 duplicates. *Evidence class:* VENDOR_DOCUMENTED_SEMANTICS. *Residual risk:* window expiry (F11); payload-conflict on re-planned ops (C13). *Deactivation:* source drops/changes key semantics.

**R2 — Native precondition preference.**
IF the invariant is source-local THEN use source-native atomic precondition+mutation; harness-side read-check-write is prohibited on that resource BECAUSE conditional writes make the race impossible at the source (S9, S30, S31, C03) UNLESS the source's precondition mechanism is known-weaker for the case (e.g., global-table LWW, S30) — then re-home the invariant or add source-side monotonic status preconditions.
*Invariant:* no lost update. *Failure prevented:* F4/F5. *Evidence:* VENDOR_DOCUMENTED_SEMANTICS + FOUNDATIONAL. *Residual:* cross-system invariants remain unproven. *Deactivation:* source loses conditional-write support.

**R3 — Outcome honesty.**
IF a consequential operation returns timeout/connection-loss/indeterminate-error THEN set effect state UNKNOWN_OUTCOME and take no retry/compensation action except per R4/R5 BECAUSE ack absence is not failure evidence (S8, S11, S23, S36, S37, C02) UNLESS the effect is proven naturally idempotent (then plain retry allowed).
*Invariant:* no decision from ambiguous evidence. *Failure prevented:* F1/F12 misuse. *Evidence:* FOUNDATIONAL + VENDOR. *Residual:* limbo duration. *Deactivation:* none (gate-level rule).

**R4 — Reconcile-before-mutate.**
IF UNKNOWN_OUTCOME and an authoritative status path exists THEN reconcile (query/webhook/settlement) before any retry or compensation BECAUSE payments/durable-runtime practice resolves ambiguity with authoritative evidence (S23, S24, S36) UNLESS the source's documented idempotency key is still validly held — identity-guarded retry may then precede reconciliation (S11).
*Invariant:* decisions from authoritative evidence. *Failure:* FC-13/FC-14. *Residual:* status lag. *Deactivation:* status path loses authority.

**R5 — No harness locks for external correctness.**
IF a stale concurrent writer would cause material harm THEN achieve exclusion via source-native conditional/monotonic state (R2) or fence-capable infrastructure BECAUSE unfenced locks provably admit stale writers and k8s-class leases explicitly do not fence (S1, S2, S19, C04) UNLESS the resource itself checks fencing tokens (then lease+fencing acceptable).
*Invariant:* no zombie write. *Failure prevented:* F6. *Residual:* token-checking resources needed. *Deactivation:* never for external SaaS; internal efficiency locks exempt.

**R6 — Durable dedup beyond native windows.**
IF duplicate_harm=MATERIAL AND (no native key OR native window < retention horizon) THEN persist logical-effect identity in HF durable dedup with retention ≥ horizon, checked before first attempt BECAUSE all native dedup windows are bounded and delayed duplicates are documented (S11, S13, C09) UNLESS the source guarantees unbounded dedup (then record the guarantee).
*Invariant:* one effect per identity, beyond windows. *Failure:* F11. *Residual:* storage lifetime vs. legal retention conflicts (OQ-5). *Deactivation:* harm class downgraded.

**R7 — Replay separation.**
IF workflow logic may be replayed THEN external effects execute only in non-replayed step/activity boundaries with recorded nondeterminism and stable identity BECAUSE vendor docs identify duplicate I/O as the replay defect class (S16, S17, S18, C11) UNLESS the effect is verified idempotent and harmless on replay.
*Invariant:* replay adds no external effects. *Failure:* F10. *Residual:* history corruption (separate class). *Deactivation:* non-replaying engine.

**R8 — Pivot-last & approval for irreversibles.**
IF an effect is NON_IDEMPOTENT_IRREVERSIBLE THEN require approval gate + execution after all fallible/reversible steps BECAUSE no inverse exists (S20, S21, C05) and forward correction is a business decision UNLESS a documented dry-run equivalent exists and is used.
*Invariant:* irreversibles only on validated states. *Failure:* F9. *Residual:* none (exposure-reduction only). *Deactivation:* effect reclassified reversible.

**R9 — Compensation contract.**
IF a step claims compensation support THEN the compensation must be a named domain operation with its own identity, authorization, idempotency, retry budget ≥ forward path, and MAY only run on decided-success outcomes BECAUSE compensation failure/danger is documented and compensation ≠ rollback (S20, S22, C05) UNLESS a source-native inverse exists (provider cancel/void within same business transaction).
*Invariant:* compensations are safe, authorized, idempotent. *Failure:* F8/FC-11/FC-13. *Residual:* compensation can still fail → escalation (F8). *Deactivation:* flow becomes single-transaction at one source.

**R10 — Receipt separation.**
IF an effect executes THEN record {attempt, identity, request evidence, response/ack, authoritative outcome evidence} as separate fields, and never write "success" from an ack alone BECAUSE ack≠outcome (C02) and receipts are the reconciliation substrate (S24, S36) UNLESS the effect is READ_ONLY (attempt log only).
*Invariant:* evidence completeness. *Failure:* all FC-01–03 forensics. *Residual:* evidence can be tampered unless integrity-protected (OQ-6). *Deactivation:* none.

**R11 — Capability discovery.**
IF a new source/effect is onboarded THEN discover {idempotency key? window? conditional write? status query? dedup semantics?} before first consequential use BECAUSE delegation decisions require capability knowledge (Section 10) UNLESS the effect is READ_ONLY.
*Invariant:* informed effect contracts. *Failure:* wrong defaults. *Residual:* docs drift → periodic re-verification. *Deactivation:* none.

**R12 — Ambiguity escalation default.**
IF UNKNOWN_OUTCOME persists past reconciliation deadline AND duplicate_harm=MATERIAL THEN escalate to a human with the evidence bundle; do not auto-decide BECAUSE practice treats unresolvable limbo as an operational state with an owner (S20, S22, S36) UNLESS business rules define a bounded auto-policy (e.g., void-after-confirmed-nonexecution).
*Invariant:* limbo has an owner. *Failure:* FC-14. *Residual:* human latency. *Deactivation:* never (safety default).

---

## 12. ANTI-PATTERNS (tested; each with evidence-based refutation)

1. **timeout = failure.** Refuted by C02 (S8, S11, S23, S37). Correct: UNKNOWN_OUTCOME + reconcile.
2. **retry until success.** Refuted for harmful effects: unbounded retry without identity duplicates effects (S13, S35). Correct: class-based retry budgets + identity guards (R1, R6).
3. **workflow durability = business exactly-once.** Refuted by C01/C10 (S15, S16, S18). Durability covers *control state*, not external effects.
4. **every effect requires an HF ledger.** Refuted by C08: reads/natural idempotents need tracing at most. Universal ledger adds write-load and false-dedup risk with no named failure prevented (minimality violation).
5. **distributed lock = safety.** Refuted by C04/C12 (S1, S19). Locks without resource-side rejection are efficiency tools.
6. **compensation = rollback.** Refuted by C05 (S20, S22). Compensation is a new forward business operation.
7. **Event Sourcing = enterprise maturity.** Refuted by C06/C20: ES is a named-requirement tool; audit ≠ event store (S25); durable runtimes implement journal/checkpoint internally without imposing ES.
8. **current state = known previous effect outcome.** Refuted: current state cannot prove the previous attempt's outcome (that's why UNKNOWN_OUTCOME exists; S36's pending/submitted_unknown model).
9. **acknowledgement loss = operation failure.** Same evidence class as #1; separated because it also corrupts *messaging-layer* designs (S35).
10. **source-native guard duplicated by weaker harness logic.** Refuted by C14: harness re-checks (non-atomic, window-limited, clock-based) add failure modes without adding strength; the harness check must never be *believed* over the source's atomic decision (S1's fencing analysis is the same shape: protection must live at the resource).

---
## 13. PROFILE A / B / C CONSEQUENCES

### Profile A — Low-risk read-only or bounded task
* Mechanisms: effect classification (READ_ONLY/IDEMPOTENT_WRITE only); free retries; request-id tracing; freshness policy for stale-sensitive reads (ETag optional, R2-inactive).
* **Not applied:** effect identity machinery, dedup stores, UNKNOWN_OUTCOME state (a failed read is just a failed read — no consequence), locks, compensation, ES.
* Activation condition to leave A: any write/consequential effect appears → contract required → Profile B rules engage.

### Profile B — Stateful multi-step workflow with moderate writes/effects
* Mechanisms: EffectContract per consequential effect; native-first delegation (R1, R2, R11); receipts (R10); UNKNOWN_OUTCOME + reconcile-before-retry (R3, R4); identity+dedup **only where duplicate_harm=MATERIAL and native coverage insufficient** (R6); optimistic versioning on HF-owned state (no leases needed while HF is single-writer).
* Not applied by default: compensation engine (per-step compensation contracts allowed when a domain op exists — R9), fencing, ES, HF lock managers.
* Activation conditions to leave B: privileged sources, irreversible effects, multi-system material flows, concurrent HF workers on shared authority → Profile C elements individually.

### Profile C — High-risk privileged consequential workflow
* Profile B **plus each of the following only under its activation condition**:
  * approval gates + pivot-last ordering (R8) — activation: irreversible or privileged effects;
  * compensation contracts with human-escalation on compensation failure (R9, R12) — activation: multi-step flows with reversible-but-material steps and a *named domain inverse*;
  * durable dedup with retention ≥ business horizon (R6) — activation: material duplicate harm, native window insufficient;
  * lease+fencing for HF-internal authority (R5) — activation: concurrent HF workers share authority over a resource that cannot enforce stale-write rejection **and** the flow can be redesigned to conditional state transitions — if it cannot, the flow is not approvable in C without a fence-capable acceptance point;
  * integrity-anchored receipt storage (OQ-6) — activation: third-party audit requirement.
* **Explicitly *not* "all mechanisms enabled":** no harness locks (R5), no exactly-once claims (C01), no universal ledger (C08), no mandatory ES (C06), no auto-compensation on unknown outcomes (FC-13).

---

## 14. FAULT-INJECTION PROGRAM (executable research/evaluation scenarios)

| # | Test | Setup | Injected failure | Expected safe behavior | Unacceptable outcome | Observable evidence |
| --- | --- | --- | --- | --- | --- | --- |
| FI-1 | Lost acknowledgement | Stub source executing write, dropping response; GUARDED/NON_IDEMPOTENT effect | Drop response after commit | State=UNKNOWN_OUTCOME; reconcile query issued; single effect | Retry creates 2nd effect; state=FAILED | Effect count at source = 1; state transitions log |
| FI-2 | Duplicate request | Same logical op delivered twice (broker replay) | Second delivery in-flight and post-window | One effect; second suppressed by native key + HF dedup | 2 effects; dedup miss | Dedup hit counter; source effect count |
| FI-3 | Crash after external success | Kill worker between call OK and record | Process kill at window | On restart: reconcile via identity; adopt outcome; no re-execution | Re-executed effect | Attempt ledger vs source truth diff = ∅ |
| FI-4 | Concurrent mutation | Two writers on same object | Interleave read/write | Loser receives precondition failure; refreshes; no lost update | Silent overwrite | Version audit trail |
| FI-5 | Stale version | Writer holds old ETag/version | State advances mid-flight | 412/ConditionalCheckFailed handled as FC-05 | Force-write succeeds | Precondition-fail event |
| FI-6 | Lease expiry | Worker A paused past lease; B acquires | Pause A (sleep) past TTL | A's post-pause writes rejected (conditional/epoch) or A abstains; B reconciles A's in-flights | A overwrites B's effect | Fencing/epoch rejections; effect count |
| FI-7 | Stale worker | Same as FI-6 with A resuming after B committed | Resume A mid-write | A's stale write fails at resource; alert raised | Stale write lands | Rejection + alert logs |
| FI-8 | Partial multi-system | Flow: A (reversible), B (fails), C (pivot) | Fail B after A commits | A compensated (authorized domain op, idempotent) or forward-recovered per classes; C never started | C started; A uncompensated silently | Per-system outcome records |
| FI-9 | Compensation failure | A committed; compensate | Fail compensation N times | Retry with own identity; then escalation state + alert; forward state consistent | Silent success claim; compensation loop without budget | Escalation event; evidence bundle |
| FI-10 | Irreversible effect | Effect class IRREVERSIBLE | Attempt to auto-compensate | Contract has no compensation field; forward-correction proposal requires approval | Auto-inverse invoked | Contract schema validation |
| FI-11 | Replay duplication | Replay-based runtime; orchestration with external call | Force replay (worker restart) mid-activity | Call not re-issued from replayed logic; activity boundary dedupes via identity | Duplicate external call from replay | Call count at stub = 1; history events |
| FI-12 | Delayed duplicate | Duplicate after native window (e.g., >24h class) | Replay op after window expiry | HF durable dedup rejects; or source monotonic precondition makes it a no-op | Effect re-applied | Dedup store hit; precondition-fail event |

Each test doubles as the falsification experiment for the corresponding promotion decision (Section 15) — e.g., FI-6/7 for R5, FI-1/3/12 for R3/R4/R6, FI-11 for R7.

---

## 15. PROMOTION MATRIX

| Mechanism | Decision | Rationale & evidence boundary |
| --- | --- | --- |
| Explicit UNKNOWN_OUTCOME state + outcome-honesty (ack≠outcome) | **PROMOTE_TO_DESIGN_PRINCIPLE** | C02; foundational (S8) + universal vendor semantics (S11, S23, S36, S37). Boundary: consequential effects (reads exempt). |
| Effect-class model with derived retry/identity/reconciliation | **PROMOTE_TO_DESIGN_PRINCIPLE** | C07/C08; RFC 9110 (S9), AWS step semantics (S18), Temporal guidance (S16). Boundary: enums are v0.1, subject to fault-injection. |
| Prefer source-native atomic precondition+mutation | **PROMOTE_TO_DESIGN_PRINCIPLE** | C03 (S9, S30, S31). Boundary: source-local invariants only; known-weak native modes excepted. |
| Receipts: separate ack vs authoritative-outcome evidence | **PROMOTE_TO_DESIGN_PRINCIPLE** | C02, R10 (S24, S36). Boundary: READ_ONLY effects need attempt traces only. |
| Ban unscoped "exactly-once" claims | **PROMOTE_TO_DESIGN_PRINCIPLE** | C01, C07, C16–C18. No boundary — terminology gate. |
| Stable logical effect identity for consequential effects, mapped to native keys where present | **PROMOTE_AS_CONDITIONAL_MECHANISM** | Activation: duplicate_harm ∈ {RECOVERABLE, MATERIAL} or flow membership; C08/C13. Boundary: identity-under-replanning unresolved (OQ-3). |
| Reconcile-before-retry/compensate protocol (R4) | **PROMOTE_AS_CONDITIONAL_MECHANISM** | Activation: UNKNOWN_OUTCOME with available authoritative query (S23, S36). |
| HF durable dedup store with retention horizon | **PROMOTE_AS_CONDITIONAL_MECHANISM** | Activation: MATERIAL harm ∧ native coverage < horizon (C09, F11). Experiment: FI-2/FI-12. |
| Lease-based execution authority for HF workers | **PROMOTE_AS_CONDITIONAL_MECHANISM** (HF-internal only, with R5) | Activation: concurrent workers; lease alone explicitly non-safety (S1, S19). Experiment: FI-6/7. |
| Compensation contracts (named domain ops, authorization, idempotency, pivot-last) | **PROMOTE_AS_CONDITIONAL_MECHANISM** (design rule R9); generic compensation **engine** = KEEP_EXPERIMENTAL | C05 (S5, S20, S22). Boundary: only decided-success outcomes; engine-level auto-inverse unsupported. |
| Event sourcing for HF internal state | **KEEP_EXPERIMENTAL** (activation conditions documented; default = checkpoint/journal + receipts, C20) | C06 (S17, S25, S33). Boundary: business-domain ES (user-facing event streams) is a separate product decision. |
| Effect-ordering guarantees across heterogeneous sources | **KEEP_EXPERIMENTAL** | No evidence found that generic cross-source ordering is enforceable; analogy only. |
| Semantic-undo inference (auto-derived inverses) | **KEEP_EXPERIMENTAL** | Research-grade only (SagaLLM-class, S5b); no production evidence. |
| HF-owned distributed lock manager (Redlock-class) for correctness | **DO_NOT_PROMOTE** | C04 (S1, S2, S19). |
| Universal per-tool-call effect ledger | **DO_NOT_PROMOTE** | C08 minimality; no named failure prevented for reads/idempotents. |
| "Exactly-once business effect" guarantee in HF contracts | **DO_NOT_PROMOTE** | C01. |
| timeout=failed / ack-loss=failed mappings | **DO_NOT_PROMOTE** | C02. |
| Harness-side re-implementation of native guards believed as *additional* safety | **DO_NOT_PROMOTE** | C14. |

---

## 16. OPEN QUESTIONS AND REVISION TRIGGERS

**Open questions (unresolved by this research — no manufactured closure):**

* **OQ-1 Lease horizons for human-latency agentic work.** Leases were designed for millisecond–second critical sections (S3). Agent steps can run minutes–hours; long leases widen skew windows. No studied system gives evidence for hour-scale leases with safety claims. *Needs: HF experiment (FI-6/7 at agentic durations).*
* **OQ-2 Classification heuristics for indeterminate errors per provider.** Stripe documents 500-replay + indeterminacy (S11); other providers differ silently. A per-source "indeterminate-error classes" registry is needed; capability discovery (R11) cannot fully automate this from docs alone.
* **OQ-3 Effect identity under bounded replanning.** When an agent re-plans and changes the payload of a "same" intended effect, fingerprint-based native dedup will 409/422 (S10, S11) and window-based dedup will miss. Where is the same-logical-effect boundary? Currently a business/semantic call — no evidence for a general rule (C13 PARTIALLY_SUPPORTED).
* **OQ-4 Materiality thresholds.** `duplicate_harm=MATERIAL` needs a risk rubric (financial? legal? reputation? irreversibility?). Not derivable from distributed-systems evidence alone.
* **OQ-5 Dedup retention vs. privacy law.** R6 demands retention ≥ duplicate horizon; GDPR-style erasure may demand deletion sooner. Tension unresolved.
* **OQ-6 Tamper-evidence for HF receipts.** If receipts feed audits, hash-chaining + external timestamping (RFC 3161-class) is indicated (S25) but unproven *for HF's evidence model*.
* **OQ-7 Reconciliation authority conflicts.** When status API, webhook, and settlement disagree (FC-14), no studied source defines a precedence rule; likely per-domain.
* **OQ-8 At-most-once + reconciliation vs at-least-once + identity for Profile C.** Both patterns are evidenced (S18 documents both); which minimizes residual risk per workload is an empirical question → EXPERIMENT_REQUIRED.
* **OQ-9 Behavioral non-determinism of LLM steps under replay.** Durable-runtime determinism constraints target code; agent steps whose "code" is a model call may re-decide differently after replan. Interaction with identity stability (OQ-3) untested.

**Revision triggers:**

1. Contract version/digest change (re-run binding check; expect CONTRACT_VERSION_CHANGED handling).
2. The IETF idempotency-key draft (or successor) becoming an RFC, or major providers changing key retention/conflict semantics (S10, S11).
3. Durable-runtime semantic changes: Temporal Nexus/dedup policies, AWS Durable Execution SDK GA changes (S18), Azure Durable Task v3-class changes.
4. First production evidence of fence-enforcing SaaS APIs (would re-open R5 for external resources).
5. HF fault-injection results contradicting any SUPPORTED claim above (esp. FI-1, FI-6, FI-11).
6. Supply of the missing knowledge artifacts (05/05.1/05.2/08) → reconciliation pass; any conflicts to be logged, not merged silently.
7. New peer-reviewed work on exactly-once effect composition or leases at agentic timescales.

---

## 17. QUALITY GATE SELF-CHECK

| Gate | How satisfied |
| --- | --- |
| Evidence gate | Every material claim cites S-register sources with evidence class (Sections 4–5). |
| Boundary gate | Native-guard claims bounded to source-local invariants (C03); EOS claims decomposed (C07, C16–C18); lease claims bounded to correctness-class (C12). |
| Counterevidence gate | Dedicated counterevidence column (Section 5); H10 tested against harness-necessity cases; C19 explicitly CONTRADICTED; antirez position represented (S2). |
| Minimality gate | Every promoted mechanism has named failure/invariant (R1–R12, Section 15 rationale); universal ledger rejected. |
| Source-native gate | R2 + Section 10 delegation conclusions; C14. |
| Exactly-once gate | C01/C07; terminology bans; vendor claims decomposed by boundary. |
| Unknown-outcome gate | C02; R3/R4; F1/F12; FC-01. |
| Retry gate | Retryability derived from effect class + identity state, not error detection (Section 9 procedure steps 3–4). |
| Compensation gate | C05, R9, FC-11/13; F8/F9. |
| Architecture-authority gate | Artifact labeled research-only; Section "ARCHITECTURE DECISIONS REQUIRING SEPARATE AUTHORIZATION" separates findings from decisions. |
| Anti-sycophancy gate | Hypotheses tested, not assumed; prior HF-facing ideas challenged where evidence demanded (universal ledger → rejected; lock ideas → rejected; ES-default → rejected; C19 webhook-sole-truth → contradicted). |

---

## SOURCE REGISTER

| # | Source | Type / evidence class |
| --- | --- | --- |
| S1 | M. Kleppmann, *How to do distributed locking* (2016), martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html | Engineering analysis of consensus-based locking; fencing-token construction; Redlock critique |
| S2 | S. Sanfilippo, *Is Redlock safe?* (antirez.com/news/101) + Hacker News thread (news.ycombinator.com/item?id=11059738) | Counterevidence position; efficiency-vs-correctness framing; CAS/fencing concession |
| S3 | C. Gray & D. Cheriton, *Leases: An Efficient Fault-Tolerant Mechanism for Distributed File Cache Consistency*, SOSP 1989 | Foundational lease paper (accessed via archival summaries) |
| S4 | P. Helland, *Life beyond Distributed Transactions: an Apostate's Opinion* (CIDR/ACM, 2007) | Entities/activities; at-most-once acceptance via remembered message identity; idempotency necessity |
| S5 | H. Garcia-Molina & K. Salem, *Sagas*, SIGMOD 1987 (via summaries/derivatives incl. arXiv 2503.11951) | Original saga model; compensating transactions; forward recovery |
| S6 | J. Gray & L. Lamport, *Consensus on Transaction Commit* (Microsoft Research, 2004); J. Gray, *Notes on Data Base Operating Systems* (1978) | 2PC blocking; uncertain state; commit as consensus |
| S7a | H. T. Kung & J. T. Robinson, *On Optimistic Methods for Concurrency Control*, ACM TODS 6(2), 1981 | OCC foundations |
| S8 | Two Generals Problem (P. Huber 1975; named by Gray 1978) — formal treatments (grokipedia/mwhittaker/bulloak analyses) | Impossibility of certain agreement over lossy links; ack regress |
| S9 | RFC 9110 *HTTP Semantics* (idempotent methods; conditional requests §13) with RFC 7232 text; http.dev analyses | Standard: method idempotency; If-Match/If-Unmodified-Since/412; lost-update prevention; validator granularity caveats |
| S10 | IETF draft-ietf-httpapi-idempotency-key-header (-03/-07, expired; greenbytes.de mirror; datatracker) | Standard-track (not RFC): key uniqueness, fingerprints, 409/422 semantics, expiry policy |
| S11 | Stripe API docs — idempotent requests & advanced error handling (docs.stripe.com) | Vendor semantics: ≥24h key retention; parameter-conflict; 500-replay & indeterminacy; key derivation guidance |
| S12 | Google Cloud Pub/Sub — Exactly-once delivery docs (docs.cloud.google.com/pubsub/docs/exactly-once-delivery) | Vendor semantics: ack-based no-redelivery; pull-only; region scope; latest-ack-id |
| S13 | AWS SQS FIFO deduplication — AWS docs & engineering analyses (adhdecode, reintech, oneuptime, joudwawad) | Vendor semantics + practice: 5-min send-side window; visibility-timeout redelivery trap |
| S14 | Apache Kafka EOS (KIP-98 semantics; Conduktor/AxonOps engineering docs) | Vendor/engineering: idempotent producer (PID+seq); transaction scope = Kafka-internal; external sinks at-least-once + idempotency; ProducerFencedException |
| S15 | Apache Flink fault-tolerance docs (nightlies.apache.org) + analyses (Streamkap, adhdecode) | Vendor semantics: exactly-once = state affected once; end-to-end requires replayable source + transactional/idempotent sink; 2PC sink constraints |
| S16 | Temporal docs — activities idempotency, error handling, workflow SideEffect API (docs.temporal.io; pkg.go.dev) | Vendor semantics: at-least-once activities; RunID+ActivityID as key; SideEffect no execution guarantee; determinism constraints |
| S17 | Azure Durable Functions — orchestrator code constraints (learn.microsoft.com / docs.azure.cn) + MS Q&A | Vendor semantics: event-sourced replay; no I/O in orchestrators (duplicate I/O warning); deterministic APIs; idempotent activities |
| S18 | AWS Lambda Durable Execution & AWS Durable Execution SDK docs — idempotency and retries (docs.aws.amazon.com) | Vendor semantics: execution names; steps at-least-once; AtMostOncePerRetry "per attempt, not per workflow"; keys minted inside steps |
| S19 | Kubernetes client-go leaderelection package docs (pkg.go.dev/k8s.io/client-go/tools/leaderelection) | Vendor semantics: no fencing guarantee; clock-skew-rate tolerance; ReleaseOnCancel caveat |
| S20 | Microsoft Azure Architecture Center — Compensating Transaction pattern (learn.microsoft.com/azure/architecture/patterns/compensating-transaction) | Vendor engineering guidance: compensation limits, idempotency, human decisions |
| S21 | Reactive Design Patterns — Saga; Richardson-derived saga/compensation material | Engineering analysis: semantic undo; unsendable-email class; isolation absence |
| S22 | Orkes Conductor — Saga compensation recipe (orkes.io) | Engineering practice: undo only completed steps; compensation idempotency & retry budgets; compensation ≠ rollback; alerting |
| S23 | Paysight — Payment gateway failover (paysight.io) | Engineering practice: timeout ≠ failure; status-check-first; attempt ledgers; canonical order identity |
| S24 | Prachub — Payment systems: ledgers, idempotency, reconciliation | Engineering practice: (merchant,key)→hash/response storage; submitted_unknown states; settlement reconciliation |
| S25 | Event-sourcing critique & decision frameworks — dev.to *Event store ≠ audit log*; baytechconsulting 2025; systemdesignplaybook; intuitionlabs | Engineering analysis: ES guarantees vs audit-log requirements; CRUD+audit alternative; activation conditions |
| S25b | Rohit, *Event Sourcing: The Append-Only Truth* (systemdesignplaybook.substack.com) | ES mechanics: sequence numbers, projections, poor-fit list |
| S31 | Lost-update analyses — abstractalgorithms (PostgreSQL RR first-committer-wins; MySQL RR caveat); adhdecode; Medium (Sandeep Verma) | Engineering analysis: read-modify-write race; CAS; isolation-level boundaries |
| S31b | MongoDB DevRel — Read-Modify-Write anti-pattern (medium.com/mongodb) | Vendor engineering: atomic operators; findOneAndModify |
| S29 | Two-phase-commit blocking analyses — singhajit.com; cs.stackexchange 76192; adhdecode | Engineering analysis of S6 semantics; heuristic decisions |
| S32 | draft-ietf-httpapi-idempotency-key-header-03 full text (greenbytes.de) | Standard-track text: 409 in-flight, 422 payload mismatch |
| S33 | Temporal blog — *Idempotency and durable execution* (temporal.io/blog) | Vendor: event-sourced internals; idempotency key patterns; at-most-once trade-offs |
| S34 | Temporal learn tutorial — standalone activities/job queue (learn.temporal.io) | Vendor: "at-least-once + idempotency = effectively-once side effects"; fresh-UUID-per-retry anti-pattern |
| S35 | OneUptime — *Consumer crashes after the side effect but before acknowledgement* (2026) | Engineering analysis: ack-loss duplicate window; ack-first trade (loss); ordering analysis |
| S36 | D. Nasyrov — *An unknown provider outcome is not a new operation* (hackmd.io/@dmytro-nasyrov) | Engineering practice: submitted_unknown modeling; identity retention; webhook semantics (Stripe/Adyen) |
| S37 | System Design Academy — *Durability: What Does COMMIT Really Promise?*; morpholog/pivota PR analyses (github.com) | Engineering practice: CommitOutcomeUnknown classes; treating commit-timeout as unknown; known-non-commit distinction |
| S38 | AWS Step Functions — Choosing workflow type / execution guarantees (docs.aws.amazon.com/step-functions) | Vendor semantics: Standard exactly-once execution model & idempotent starts; Express at-least-once; 90-day name retention |
| S39 | Dual-write/outbox pattern analyses — singhajit.com; technori; codewiz.info; streamkap | Engineering practice: no cross-system transaction; outbox = local atomicity, at-least-once relay |
| S40 | kwahome — *Distributed Systems: Transactions, Atomic Commitment, Sagas*; conduktor saga glossary | Engineering analysis: backward/forward recovery; pivot/retryable/compensable taxonomy; isolation limits |
| S41 | macro PR #7301 analysis (SetupIntent identity, two-tab race, winner election) | Engineering practice example: request-identity vs logical-effect identity collision across concurrent flows |

*Sources accessed 2026-09-19 via live web research. Classification per Evidence Classes; vendor docs = VENDOR_DOCUMENTED_SEMANTICS; foundational papers accessed through reputable archival copies/summaries where noted.*

---

## VALIDATED FINDINGS

1. **Outcome honesty:** absence of success ack ≠ failure; consequential effects require explicit `UNKNOWN_OUTCOME` and reconciliation before retry/compensation (C02, H3, H4).
2. **Durable workflow execution does not imply exactly-once external business effects**; effect-level safety requires target-side idempotency/dedup ("effectively-once", C01, C10, H1).
3. **Source-native atomic precondition+mutation is the correct mechanism for source-local invariants**; harness read-check-write is unsafe by construction (C03, H2).
4. **Exactly-once must be decomposed by boundary** (delivery/processing/effect); end-to-end effect exactly-once does not exist without target cooperation (C07, H9).
5. **Unfenced distributed locks/leases cannot prevent stale writers**; correctness requires resource-side rejection (fencing or conditional state) (C04, C12, H6).
6. **Compensation is a new, authorized, idempotent business operation**, not rollback, and can fail or be impossible (C05, H7).
7. **Stable effect identity is required for a *selected* effect class** (harmful non-idempotent effects), not every invocation (C08, H5).
8. **Delayed duplicates beyond native windows are real**; dedup retention must be chosen from the business duplicate horizon (C09).
9. **More harness machinery can reduce reliability** where sources expose stronger native guarantees; delegate, then track evidence (C14, H10).
10. **Replay-based runtimes require external effects to live outside replayed logic** with stable, recorded identity (C11).

## PARTIALLY SUPPORTED FINDINGS

1. **Effect identity under re-planning (C13/OQ-3):** identity stability rules exist operationally in payments/API practice, but no general rule for "same logical effect" under payload-changing replans.
2. **Indeterminate-error classification per provider (OQ-2):** Stripe-class guidance exists; general heuristics are practice, not standard.
3. **Leases at agentic timescales (OQ-1):** lease theory and vendor practice cover short windows only.
4. **Event sourcing for audit (C06 boundary):** ES *does* provide change history within one trust domain; third-party audit claims require additional machinery.

## CONTRADICTED OR REJECTED ASSUMPTIONS

1. **"HF can rely on provider webhooks as sole outcome truth" — CONTRADICTED** (C19): webhooks are at-least-once, unordered evidence inputs.
2. **"Every tool invocation needs an HF ledger entry" — REJECTED** (minimality, C08).
3. **"Distributed lock = safety" — REJECTED** for correctness-class use (C04).
4. **"Event sourcing as default/enterprise maturity" — REJECTED** as default (C06, C20).
5. **"timeout/ack-loss = operation failure" — REJECTED** (C02).
6. **"Workflow durability ⇒ business exactly-once" — REJECTED** (C01).
7. **"Harness-side guards stack on native guards for more safety" — REJECTED as believed redundancy** (C14: weaker checks add failure modes, not strength).

## CONDITIONAL HF MECHANISMS

* Stable logical-effect identity + native key mapping (activation: consequential effects w/ duplicate harm; R1, R6).
* Reconcile-before-mutate protocol (activation: UNKNOWN_OUTCOME with authoritative query; R4).
* HF durable dedup store with retention ≥ business horizon (activation: material harm ∧ insufficient native coverage).
* Lease-based HF-internal execution authority with fencing/conditional-write gatekeeping (activation: concurrent workers; R5).
* Compensation contracts as named domain operations (activation: reversible material steps with domain inverses; R9).
* Approval gates + pivot-last ordering (activation: irreversible/privileged effects; R8).
* Capability discovery per source (R11) — supporting mechanism for all of the above.

## EXPERIMENTAL ITEMS

* Generic compensation engine (auto-orchestrated compensations) — keep out of design until FI-8/FI-9 pass at Profile C workloads.
* Semantic-undo inference for LLM-generated operations.
* Cross-system effect ordering guarantees.
* Event sourcing as HF internal state model (only if activation conditions appear; C20).
* At-most-once+reconciliation vs at-least-once+identity pattern selection per workload (OQ-8).

## INSUFFICIENT EVIDENCE

* Lease safety at hour-scale agent step durations (OQ-1).
* Generalizable rule for same-logical-effect identity under payload-changing replanning (OQ-3).
* Materiality rubric for duplicate harm (OQ-4) — business input required.
* Precedence rules for conflicting authoritative evidence (OQ-7).
* Determinism/replay interaction with LLM step re-decision (OQ-9).
* Tamper-evidence requirements for HF receipts in regulated contexts (OQ-6) — direction indicated (S25), adoption unproven for HF.

## REQUIRED HF EXPERIMENTS

1. **FI-1/FI-3/FI-12** (lost ack, crash-after-success, delayed duplicate) on the HF effect executor + one payments-class stub and one database-class source: validates R1/R3/R4/R6.
2. **FI-6/FI-7** (lease expiry / stale worker) with hour-scale leases: validates R5 boundary and OQ-1.
3. **FI-11** (replay duplication) on the chosen durable runtime: validates R7.
4. **FI-2** duplicate burst incl. payload-variant duplicates: probes OQ-3 identity rules.
5. **FI-8/FI-9/FI-10** partial flow + compensation failure: validates R8/R9 and the no-auto-compensation-on-unknown rule.
6. **OQ-8 pattern A/B:** same Profile C workload implemented both ways; measure residual duplicate events and limbo durations.
Each experiment must publish: hypothesis, falsifier, measured residual failure, and a promotion-matrix delta proposal.

## PROPOSED KNOWLEDGE-BASE DELTAS

1. Add **Canonical Terminology v0.1** (Section 3) to the HF glossary; ban unscoped "exactly-once" in all HF documents.
2. Add **Failure Taxonomy v0.1** (Section 6, FC-01…FC-15) as the HF incident/classification vocabulary.
3. Add **Effect/Retry/Reconciliation Decision Contract v0.1** (Section 9) as the candidate schema for Runtime/Effect/Recovery/Validation contract generation.
4. Record **Source-Native Guard Capability Matrix** (Section 10) as onboarding template for new sources (with R11 discovery checklist).
5. Record **Architecture Decision Rules R1–R12** (Section 11) as candidate rules pending separate architecture authorization.
6. Amend prior artifacts (when supplied for reconciliation): durable-execution material must state the activity-level at-least-once/duplicate caveat explicitly (H1); state-ownership material should note the source-native preference (H2, H10).
7. Record fault-injection program (Section 14) as the standing evaluation suite for effect-machinery changes.

## ARCHITECTURE DECISIONS REQUIRING SEPARATE AUTHORIZATION

* Adopting the Decision Contract fields as binding HF contract schema (beyond v0.1 candidate status).
* Choosing the HF internal state model (checkpoint+journal default vs ES) — product-level decision.
* Enabling compensation in any Profile C flow (authorization semantics are business decisions).
* Any lease/fencing deployment for HF worker authority.
* Dedup retention periods (legal/privacy sign-off, OQ-5).
* Approval-gate UX and authority model for irreversibles (R8) — governance decision.
* Terminology bans enforcement in templates/linters (process decision).

## FINAL RESEARCH STATUS

**`PARTIAL_PROMOTION_EXPERIMENT_REQUIRED`**

Basis: design principles (outcome honesty, boundary-decomposed semantics, source-native preference, effect classification, receipts) are well-evidenced and stable (`SUPPORTED`, HIGH/MEDIUM confidence). All conditional mechanisms (identity/dedup, reconciliation protocol, leases/fencing, compensation contracts) carry named activation conditions but require the fault-injection program (Section 14 / Required HF Experiments) before design promotion; several questions are declared INSUFFICIENT_EVIDENCE rather than closed. Research findings are not an architecture baseline; nothing herein modifies Jira/Confluence.

---
