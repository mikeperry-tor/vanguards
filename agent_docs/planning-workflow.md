# Planning workflow

Use this guide with [AGENTS.md](../AGENTS.md) for staged modernization and Tor
qualification work. Keep active task plans under `agent_docs/plans/`.

## Define the plan

Record the working branch, baseline SHA and any relevant local changes, scope,
current behavior, intended outcomes, and operator and security contracts to
preserve. Identify open decisions, including explicitly supported Python, Stem,
and Tor versions, legacy state and configuration compatibility, and the role
of Tor's built-in Vanguards alongside addon-managed guards. Verify assumptions
against the checkout, the chosen image, and authoritative Tor documentation.
Distinguish observations on the baseline, external reports, proposed behavior,
and unresolved assumptions. Record explicit deferrals. When starting from a
bug report or PR, link it and record the known affected versions, the evidence
that applies to the chosen runtime, and the expected result of the relevant check.

Use one plan for work with a shared acceptance decision. When workstreams need
independent acceptance or scheduling, use a short coordinating plan for
the shared baseline, support decisions, dependencies, and final acceptance.
Keep implementation steps and detailed evidence in the owning plans and link
to them. Reconcile other active plans before changing shared interfaces or
fixtures.

Give phases stable identifiers and define their order, dependencies, coherent
commit boundaries, affected entry points, deliverables, and observable acceptance
checks. Identify the permanent documentation for each change and update it with
the implementation and applicable tests. For modernization, use these boundaries
where they fit the work.

1. **Baseline.** Record what runs today, the dependency and tooling
   versions, pre-existing failures, and the current control, consensus, and
   state contracts. Record the proposed support matrix and how it will be
   exercised.
2. **Python and packaging.** Modernize build, install, and test tooling in
   coherent changes. Verify source execution and a clean artifact install.
   Update installation and test instructions alongside their implementation.
3. **Tor harness.** Establish a repeatable Docker fixture with a pinned image
   and sanitized diagnostics. Verify authenticated control and the required
   filesystem access in the topology the tests will actually use. Run a small
   probe as soon as the required runtime and entry point work so its results can
   inform the remaining work.
4. **Compatibility and qualification.** Make focused controller changes
   justified by probe or test results. Run the affected scenarios against
   the agreed matrix and document the configurations and behaviors that
   passed, along with limitations.

Before substantive implementation, tell the user the working branch, baseline,
and plan paths. Commit the plan locally when working in a commit-based workflow.
Schedule the design and final combined reviews under the
[independent subagent workflow](../AGENTS.md#independent-subagent-workflows).
Add intermediate review at meaningful boundaries, such as a change to consensus
access or ownership of Tor settings. For each checkpoint, name the phase,
affected consumers, evidence required, and conditions for proceeding.

## Define qualification evidence

Choose scenarios for the claimed support and record the expected result for
each. Use the [local Docker rules](../AGENTS.md#local-docker-integration).

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

## Implement, review, and close

- Keep phase identifiers and acceptance criteria through review. Update status
  and evidence in place as work is implemented, validated, and reviewed. Record
  material changes in direction and their rationale. Keep the tested snapshot,
  commands, Python and Stem versions, Docker version, image digest and platform,
  actual Tor version, config or mode, and results needed to substantiate
  acceptance or explain gaps. Keep raw logs and generated output in private or
  disposable storage. Use concise summaries and omit attempt-by-attempt chronology.
- Apply the [review method](../AGENTS.md#review-method) at each checkpoint.
  Record the reviewed revision, material findings, their dispositions, and any
  correction SHAs. Keep the plan and correction history through review rounds.
  Resolve material findings before dependent work or final acceptance. Re-run
  affected checks and reopen affected reviews when changes invalidate their
  evidence. Reuse applicable results.
- Review the final combined snapshot, including corrections and any relevant
  unchanged callers. If independent review or a required check is unavailable,
  record the missing evidence and continue with the checks that are possible.
  Report implementation, validation, and review status at handoff with the
  branch and reviewed SHA or working snapshot.
- After acceptance, verify that the READMEs and relevant maintained guides
  describe current behavior, qualification scope, and durable limits. Update the
  index in `AGENTS.md` when guide paths change. Preserve the plan record in Git
  history and remove the completed plan from the working tree. Update links in
  any coordinating or dependent plans as part of cleanup. Keep deferred work
  explicit with a concrete next step and acceptance check. Use the working
  branch for plan history and cleanup, subject to the user's Git instructions.
