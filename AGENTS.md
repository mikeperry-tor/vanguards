# Development guidance for Vanguards

Vanguards is a Python/Stem controller addon for C Tor. It manages onion-service
guard layers and monitors circuit, bandwidth, and rendezvous behavior.

Support and qualify maintained C Tor releases from 0.4.9 onward. Earlier
series are end of life and outside the compatibility contract. Verify
historical version, dependency, and configuration claims against the checkout
and the selected runtime.

## Where to start

Read the guides that apply to the task.

| Reference | Purpose |
| --- | --- |
| [Accepted Tor receive behavior](agent_docs/tor-receive-behavior.md) | Start here for Bandguards or Tor receive reviews. It records the accepted limits of dropped-cell accounting on half-closed streams and linked Conflux exit circuits, and explains the scope of first- and second-hop padding. |
| [Planning workflow](agent_docs/planning-workflow.md) | Use when asked for a plan, when continuing one, or when a later stage depends on an earlier design or qualification result. It covers working plans, review rounds, and the option to request a plan-free delivery branch. |
| [README](README.md) | Operator entry points, installation, configuration, and operation. |
| [Technical README](README_TECHNICAL.md) | Defense rationale, behavior, and practical limits. |
| [Security README](README_SECURITY.md) | Threat model and logging guidance. |
| [Test README](README_TESTS.md) | Supported test commands and what the local and live tests cover. |

Use the accepted receive behavior as the baseline for reviews. Report changes
in end-to-end acceptance, accounting, or compensating controls. For an
existing limitation, explain what new evidence changes the earlier assessment.

## Engineering rules

### Investigation and scope

- Prefer the simplest complete change. First ask whether a responsibility can
  be removed or left with the component that already owns it. Before adding a
  dependency, service, abstraction, setting, or persistent state, identify what
  it must do and why existing Python, Stem, Tor, or Docker behavior is insufficient.
- Establish the failure and known affected versions before changing behavior. Keep
  necessary prerequisites focused and track unrelated findings separately.
  Scope checks, fallbacks, and retries to the affected operation. Before adding
  a fallback for Tor or Stem behavior, verify how the relevant component handles
  the input. Review effects on the defenses and guard state involved.
- Use the local C Tor checkout at `reference_repos/tor/` as a read-only
  compatibility reference for Tor behavior. If a task calls for that reference
  and the checkout is absent, tell the user which path is missing. Continue
  with the selected release's source where available. Report what you verified
  and explain which further comparison, if any, the user can enable by placing
  the matching checkout there.
- Start with `doc/man/tor.1.txt` and
  `src/app/config/` for torrc options, defaults, and validation,
  `src/feature/control/` for control commands, replies, and events, and
  `src/core/or/` for circuit behavior, dropped or ignored cell handling, and
  bandwidth accounting relevant to Bandguards. Cross-check the implementation
  with Tor's tests where relevant. Record the checkout revision when citing a
  finding, check it against the Tor release in the selected Docker image, and
  confirm affected behavior on that image.

### Controller behavior and state

- Trace the affected path through the real entry points before editing.
  The source launcher is `src/vanguards.py` and the installed `vanguards`
  command calls `vanguards.main:main`. Check CLI, config file and environment
  precedence, TCP and Unix socket support, and one-shot versus long-running
  operation where affected. Keep the example configuration, man page, and
  READMEs aligned with operator-visible changes.
- Keep mechanical Python, dependency, and packaging changes separate from
  deliberate changes to guard selection, rotation, circuit handling, or Tor
  settings. When the task changes Python, Stem, or Tor support, record that
  decision and update the relevant metadata, install paths, and test instructions.
  Preserve documented interfaces and existing state across upgrades unless
  the agreed scope changes their contract.
- Follow Tor state through authentication, startup without a consensus,
  consensus updates, reload, reconnect, and shutdown as applicable. Check
  which settings and events the selected Tor actually supports and which
  features rely on them. Treat Tor's built-in Vanguards behavior and the
  addon's explicit layer configuration as distinct modes and verify ownership
  of their settings before drawing compatibility conclusions.
  [Tor control protocol](https://spec.torproject.org/control-spec/index.html)
  · [Tor Vanguards specification](https://spec.torproject.org/vanguards-spec/index.html)
- Preserve defense defaults, state continuity, and intentional exclusions.
  Review any change that can weaken protection, close legitimate circuits,
  or rotate guards unexpectedly. Make incompatible Tor settings or missing
  capabilities visible. When changing persisted state, cover existing state
  and interruption or retry as applicable. Load pickle state only from
  trusted, locally controlled sources.
- For event-handler changes, check how processing time, retained state, and
  logging grow during a burst of events. Justify new limits and timeouts
  against the defense they protect and the legitimate traffic they affect.
- Keep passwords, cookies, keys, and production data out of fixtures and
  evidence. Redact relay fingerprints, circuit paths, and onion addresses from
  shared logs and reports.

## Independent subagent workflows

Use independent subagents for substantive design, audits, and implementation
review, including work that proceeds without a plan. Scale the review to the
change. A small, self-contained documentation edit can use focused validation.

### Independence and coordination

- Start each independent review in a fresh subagent conversation without
  inherited turns when supported. Choose reviewers who did not author the
  changes. Keep review and audit agents read-only.
- Give reviewers a self-contained brief with intent, scope, baseline, preserved
  contracts, relevant guides, and known limitations. Identify the exact SHA or
  the snapshot by base SHA, exact diff, and contents of new files. Provide
  available validation evidence and relevant plan references.
- Give each auditor a distinct question. Have them identify what their method
  can establish and where coverage ends. Assign gaps between reviews, such as
  whether an event registered at startup reaches the tested handler.
  Give delegated implementation edits explicit file ownership and coordinate
  checks that share a checkout, Docker network, or test state. Reuse recorded
  validation unless a finding or changed input calls for a focused rerun.
  Choose reviewer coverage based on the affected contracts and avoid duplicate
  reviews of the same scope and revision.
- The coordinating agent owns findings, scope, validation, and completion. If
  independent review is unavailable, finish the checks that are possible and
  identify the review gap at handoff. Tell the user what independent check
  would close it.

### Required reviews

- Review the design or audit scope before substantive work. Resolve material
  findings before relying on the affected decisions.
- For substantive work, independently review each implementation commit
  and each fixup at its exact SHA, including its affected consumers. For
  uncommitted work, correct defects introduced by the patch in that patch and
  review the resulting commit at its exact SHA. Use
  `git commit --fixup=<introducing-SHA>` for defects introduced in the working
  series. Give an in-scope defect inherited from the baseline a standalone
  commit explaining the defect and correction.
- Review the combined change at meaningful integration boundaries and before
  completion. Include relevant unchanged consumers and all prior findings and
  corrections. A single review can cover a phase and an integration checkpoint
  when its scope covers both. Later changes reopen affected reviews.
- At planned handoff, tell the user whether the working branch is ready for
  another review round or for a request to prepare a plan-free delivery branch.
  Follow the [planning workflow](agent_docs/planning-workflow.md) for both.

### Review method

- Ask design and implementation reviewers to look for concrete simplifications.
  A proposal is worth acting on when it removes a demonstrated source of
  fragility, duplicate enforcement, or state that two paths must keep in sync.
  Identify what can go away, which callers rely on it, and what evidence shows
  their defense, compatibility, and recovery guarantees still hold.
- Verify assumptions against the checkout, pinned dependencies, and effective
  Tor and Docker configuration. Before adding or removing a check, identify
  whether Vanguards, Stem, or Tor owns the guarantee and verify it against the
  implementation and tests for the affected versions and modes. Compare the expected
  behavior, implementation, tests, and documentation.
- Trace affected entry points, callers, and failure paths beyond the diff.
  Check relevant authentication, guard ownership, consensus access, circuit
  actions, reload, reconnect, and state continuity. Ask what happens on both
  success and failure, including unintended effects and what the tests can
  actually establish.
- Use the maintained guides to establish the baseline. Record an independent
  assessment before reading the author's rationale for the current change or
  other reviews of it. Then reconcile it with the plan, deviations from it, and
  prior findings and fixes. Look for repeated assumptions, cross-component
  hazards, and coverage gaps elsewhere in the affected paths. If successive
  fixups compensate for the same ownership or lifecycle problem, reconsider
  that design before adding another exception. Record findings with evidence,
  scope, and review limits. Resolve material issues and explain which proposed
  simplifications to apply, defer, or decline and why.

## Validation

- Run focused tests first, then the affected suite. Follow
  [README_TESTS.md](README_TESTS.md) for isolated source-tree tests and use
  [tox.ini](tox.ini) for the installed-wheel matrix. Package requirements are
  declared in [pyproject.toml](pyproject.toml). The checkout installer and
  qualification fixtures use the pins in [requirements.txt](requirements.txt).
  Record actual versions and baseline failures.
- Keep unit tests independent of Docker and the public Tor network. Use
  controlled fixtures for event parsing, defense decisions, and failure paths.
  Exercise the production logic responsible for the behavior under test. Where
  practical, show that a focused regression fails on the baseline and passes
  with the fix. Check for unintended effects where applicable, such as writes to
  settings the addon does not own or closure of legitimate circuits.
- When packaging changes, build and install the artifact in a clean environment
  and exercise the installed command. Documentation-only changes call for
  document, link, and whitespace checks.
- Run affected Tor contracts through the local Docker workflow. Record the
  observed checks, environment, and gaps, including the guard ownership mode
  and consensus flavor when relevant. A passing mocked test establishes
  behavior for its fixture. A passing control smoke test establishes the
  exercised control operations. Qualify service or circuit behavior with
  observations at those layers. Inspect diagnostics and skips to confirm the
  intended checks actually ran. If a required check remains unavailable, tell
  the user which claim is still open and what would let it be checked. For
  example, point to the pinned Chutney fixture when onion-service behavior
  still needs qualification.

### Local Docker integration

- Reuse the control smoke test and private Chutney onion-service fixture under
  `tests/integration/` for live Tor qualification. Keep any extensions focused
  on the fixtures, lifecycle, and assertions the agreed scenarios require.
  Prefer explicit fixture helpers and Docker's lifecycle controls.
- Start with the digest-pinned image and targets in the
  [integration Dockerfile](tests/integration/Dockerfile). Each fixture runs
  in a single container with `--network none` and starts Tor with its own
  configuration. [GitHub Actions](.github/workflows/ci.yml) runs them on Linux
  ARM64. For a new image or topology, check the effective entrypoint, torrc,
  listeners, and healthcheck. Record the image digest, platform, and actual
  `tor --version`.
- Use disposable Tor data, addon config, and addon state. Pass the controller
  an explicit endpoint and use test-only authentication. For multi-container
  tests, use a run-specific private network. If the controller runs on the
  host, publish only the required ports on host loopback and verify that the
  Tor listener is reachable through the mapping.
- Check filesystem access as well as network access. The addon reads
  `cached-microdesc-consensus` by default and `cached-consensus` when
  `UseMicrodescriptors 0` is set. It uses Tor's `CacheDirectory` when set and
  `DataDirectory` otherwise, and checks the file against Tor's control
  responses. For a separate controller, make the applicable absolute path
  readable in its filesystem. Prefer a narrow, read-only mount with a
  separate writable addon state path.
- Verify readiness with authenticated control probes and, for bootstrapped
  cases, bootstrap status and the consensus input the addon needs. Use bounded
  waits and capture sanitized diagnostics on failure. Keep public-network
  bootstrap and onion-service traffic opt-in, with disposable identities and
  test traffic. Tear down run-owned containers, networks, and temporary
  volumes, including after failure.

## Documentation update rules

- Keep `README*` user-facing. Cover what the addon does, installation,
  configuration, operation, defense rationale, and practical limits. Keep
  supported test commands in `README_TESTS.md` for users who want to verify
  their installation or checkout. Put agent instructions, contributor
  procedures, and internal qualification methods under `agent_docs/`.
- Update the owning section in place when behavior or support changes. State
  the current contract, tested versions and modes where relevant, and known
  limits. Keep development journals, dated probe narratives, review logs, and
  phase histories out of maintained guides. Active plans hold concise evidence
  and decisions needed for completion. Git history preserves completed work,
  and raw logs and generated reports belong in private or disposable storage.
- Update the reference table when adding or moving a maintained agent guide.
  Treat imported guides as references. Keep reference checkouts read-only and
  put build and runtime state elsewhere.

## Git and workspace care

- Preserve unrelated tracked, untracked, and ignored files. Stage only
  intended paths when committing.
- Follow task authorization for pushing, merging, publishing, or using live
  service infrastructure.
