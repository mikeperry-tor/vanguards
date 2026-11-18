# Planning, review, and delivery workflow

Use this guide for planned work under [AGENTS.md](../AGENTS.md). Keep the task
plan, intermediate review plans, and review records on the working branch under
`agent_docs/plans/`. List their exact paths in the task plan and update the list
as review proceeds. Use it to identify the temporary material to filter from
final squashed review and delivery. Preserve unrelated plans and permanent guides.

## 1. Introduce the working plan

Tell the user the working branch, baseline SHA, and paths to the plan and
review record. Name the intended delivery branch if known. Explain that the
working branch retains review history and that, after review, they can ask for
a separate plan-free branch. For a plan-only request, hand back the reviewed
plan and identify the first implementation step the user can request.

### Scope and acceptance

Record the working branch, baseline SHA and any relevant local changes, scope,
current behavior, intended outcomes, and operator and security contracts to
preserve. Identify the decisions the task requires and the evidence needed to
resolve them. Verify assumptions against the affected implementation and its
applicable references.
Distinguish observations on the baseline, external reports, proposed behavior,
and unresolved assumptions. Record explicit deferrals. When starting from a
bug report or PR, link it and record the known affected versions, the evidence
that applies to the chosen runtime, and the expected result of the relevant check.

Use one plan for work with a shared acceptance decision. When workstreams need
independent acceptance or scheduling, use a short coordinating plan for
the shared baseline, decisions, dependencies, and final acceptance.
Keep implementation steps and detailed evidence in the owning plans and link
to them. Reconcile other active plans before changing shared interfaces or
fixtures.

Choose phases from the requested outcomes and the dependencies between them.
Give each phase a stable identifier, coherent commit boundaries, and observable
acceptance checks. When removing behavior, keep any required replacement or
recovery path in the same commit. Identify affected entry points, tests, and
permanent documentation.

### Evidence for Tor behavior and support claims

When the task makes a claim about Tor behavior or support, select the scenarios
that exercise that claim. Record the expected result for each. For live checks,
use the [local Docker rules](../AGENTS.md#local-docker-integration).

| Layer | Evidence to collect |
| --- | --- |
| Offline regression | Focused tests and the relevant unit suite, including affected config precedence, existing state, event parsing, and defense decisions. |
| Control connection | The intended test endpoint accepts authentication and rejects bad credentials. Record the running Tor version and check required settings and event subscriptions. |
| Bootstrapped controller | Run the real entry point with a usable consensus. For addon-managed guards, verify the settings Tor actually applies and the state the addon writes. Cover relevant failures such as missing consensus access or a rejected setting. |
| Long-running controller | Observe relevant Tor events reaching their handlers. Exercise reload, disconnect and reconnect, or restart with prior state as applicable. Verify effective settings and protection after recovery. |
| Onion-service behavior | For end-to-end claims, exercise a disposable v3 onion service from a separate test client. Assert successful application traffic and the circuit or protection behavior named in the claim. Record the mode exercised, including built-in or addon-managed guards where relevant. |

Use synthetic event fixtures for targeted defense decisions that are impractical
to trigger deterministically in a live run. For consensus changes, distinguish
unavailable input from present input with missing optional fields. Cover the
affected startup and refresh paths, state preservation, and recovery when
usable input returns. Check both the expected effect and any prohibited side
effects named in the plan. Record bootstrap, dependency, and capability failures
distinctly. A skipped, blocked, or unexercised scenario remains a coverage gap.
Describe support in terms of the versions, modes, and behavior actually tested.

## 2. Review the design before implementation

Plan intermediate reviews at meaningful boundaries, such as a change to
consensus access or ownership of Tor settings. For each, record the phase or
commit boundary, affected consumers, review questions, required evidence, and
conditions for proceeding. Link any separate intermediate review plan from
the task plan. Schedule the final combined and squashed reviews and commit
the plan on the working branch.

Have an independent reviewer challenge the approach, its assumptions, and the
proposed acceptance evidence. Apply the [review method](../AGENTS.md#review-method)
to identify responsibilities the design could drop and the evidence needed to
preserve their contracts. Revise the plan for accepted simplifications and
resolve material findings before relying on the affected decisions.

## 3. Implement and review the working branch

- Keep phase identifiers and acceptance criteria through review. Update status
  and evidence in place as work is implemented, validated, and reviewed. Record
  material changes in direction and their rationale. Record the tested snapshot,
  commands, results, and environment details needed to interpret them. For Tor
  qualification, include the Python, Stem, Tor, and Docker versions, image
  digest, platform, and configuration or mode exercised. Keep raw output in
  disposable storage. Use concise summaries and omit attempt-by-attempt chronology.
- Follow the [independent review requirements](../AGENTS.md#required-reviews)
  for each implementation commit and fixup. Commit concise findings, their causes, correction
  SHAs, and validation evidence in the working review record. At intermediate
  and final combined review, trace accumulated fixes through affected consumers.
  Check for the same cause elsewhere, including in unchanged paths. Address
  material findings and accepted in-scope simplifications on the working
  branch. Use the scheduled combined review to assess the result. Repeat it
  when corrections change the reviewed implementation. Reuse valid results,
  rerun affected checks, and reopen affected reviews.
  Resolve material findings before dependent work.
- At final combined review, match each planned outcome to delivered behavior,
  the check that exercised it, any relevant versions and modes, and any gap or
  deviation. Verify the READMEs and owning guides describe the qualified
  behavior and its limits. Give deferred work a next step and acceptance check.
  If required evidence is unavailable, finish the available checks and report
  which acceptance criteria remain open. Tell the user what would close the
  gap, such as running the affected fixture against the selected Tor image.

## 4. Review the final squashed change

After combined review resolves the accumulated findings, give a fresh,
independent reviewer the implementation as a single net change against its
original baseline. Use a temporary checkout. Filter this task's changes to
the listed plan and review paths from both the snapshot and the diff, including
intermediate review plans. Verify the rest of the tree matches the reviewed
working revision, including tests and permanent documentation.

Give the reviewer the intent, constraints, and validation gaps. Have them trace
the resulting behavior through affected callers and record an initial assessment
before consulting the working record to reconcile prior findings and fixups.

Also apply the simplification review criteria to the net change. Correct
actionable findings on the working branch, repeat affected checks and combined
review, and give the updated snapshot to a fresh reviewer. Finish when the exact
snapshot meets its acceptance criteria, actionable findings are resolved, and no
evidenced, in-scope simplification warrants another change before delivery.
Record the baseline, working SHA, excluded paths, and outcome. Track unrelated
ideas separately so they do not prolong review.

## 5. Hand the working branch back for review

At handoff, identify the working branch and reviewed SHA, the results of both
final reviews, and any outstanding findings or checks. Keep the plans, review
records, and unsquashed history available for further rounds. Later implementation
changes reopen the affected reviews, including final squashed review.
Invite another review round. Once the required reviews and checks pass, tell
the user “Say ‘Prepare the delivery branch’ to have the plan-free commit
series assembled and independently reviewed against the agreed base.”

## 6. Prepare a delivery branch on request

1. On explicit request to prepare delivery, tell the user which source and
   destination branches you will use. Record the working baseline and agreed
   delivery base SHAs.
   Start a separate branch at the delivery base. Reconstruct coherent commits
   with the implementation, regression tests, and permanent documentation.
   Preserve authorship and attribution. Fold fixups into their introducing
   commits in the new series. If the introducing change is already in the
   delivery base, carry the outstanding correction as a standalone commit.
2. Omit this task's plans, intermediate review plans, and review records from
   **every new commit**. Split mixed patches and omit plan-only commits. Check
   the entire new ancestry for temporary material, including files added and
   later deleted. Preserve the original working branch and its history.
3. With a common base, verify the delivery tree matches the reviewed squashed
   snapshot. If the base advanced, compare each series against its own base,
   account for changes already upstream, identify adaptations, and rerun
   affected checks. Carry forward validation only for equivalent source and
   configuration.

## 7. Review and hand off the prepared branch

1. Give a non-author both branches, both bases, the working-to-delivery SHA
   mapping, and validation evidence. Independently review every new exact SHA
   and the combined delivery branch, including affected consumers. Apply the
   [review method](../AGENTS.md#review-method) before reconciling the result
   with the working record. Return substantive findings to the working branch
   for correction and affected reviews, then rebuild and review the delivery
   series. Keep the SHA mapping with the working review record.
2. Report both branches and reviewed SHAs, validation reused or rerun, and
   any remaining findings. Mark the prepared branch ready to merge only after
   its review and acceptance checks pass. Tell the user which branch they can
   inspect or ask to have pushed or merged. Pushing and merging each require
   user authorization.
