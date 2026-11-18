# Development guidance for Vanguards

Vanguards is a Python/Stem controller addon for C Tor. It manages onion-service
guard layers and monitors circuit, bandwidth, and rendezvous behavior. Start
with [the README](README.md) for operator entry points,
[the technical README](README_TECHNICAL.md) for defense rationale,
[the security README](README_SECURITY.md) for the threat model and logging
guidance, and [the test README](README_TESTS.md) for existing test commands.
Verify historical version, dependency, and configuration claims against the
checkout and the selected runtime.

## Documentation

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
- Index maintained agent guides here by purpose when adding or moving them.
  Use the [planning workflow](agent_docs/planning-workflow.md) when asked for a
  plan or when work spans staged changes to packaging, runtime support, Docker
  qualification, or Tor behavior. Read it before creating, materially revising,
  implementing, or closing a plan. Find active plans under `agent_docs/plans/`.
  Treat imported guides as references. Keep reference checkouts read-only and
  put build and runtime state elsewhere.

## Engineering rules

- Prefer the simplest complete change. Reuse existing code and native Python,
  Stem, Tor, and Docker behavior where they meet the requirement. Before adding
  a dependency, service, abstraction, setting, or persistent state, identify
  the concrete responsibility and why an existing component cannot own it.
- Establish the failure and known affected versions before changing behavior. Keep
  necessary prerequisites focused and track unrelated findings separately.
  Scope checks, fallbacks, and retries to the affected operation. Before adding
  a fallback for Tor or Stem behavior, verify how the relevant component handles
  the input. Review effects on the defenses and guard state involved.
- A live Tor integration harness is in scope. Keep it focused on the fixtures,
  lifecycle, and assertions the agreed scenarios require. Prefer a small
  Docker setup and explicit helpers where needed. Avoid generic orchestration,
  adapter layers, and custom lifecycle or reporting frameworks.
- Trace the affected path through the real entry points before editing.
  The source launcher is `src/vanguards.py` and the installed `vanguards`
  command calls `vanguards.main:main`. Check CLI, config file and environment
  precedence, TCP and Unix socket support, and one-shot versus long-running
  operation where affected. Keep the example configuration, man page, and
  READMEs aligned with operator-visible changes.
- Keep mechanical Python, dependency, and packaging changes separate from
  deliberate changes to guard selection, rotation, circuit handling, or Tor
  settings. Declare Python, Stem, and Tor support decisions in the plan and
  update the relevant metadata, install paths, and test instructions together.
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
- Use the local C Tor checkout at `reference_repos/tor/` as a read-only
  compatibility reference. Start with `doc/man/tor.1.txt` and
  `src/app/config/` for torrc options, defaults, and validation,
  `src/feature/control/` for control commands, replies, and events, and
  `src/core/or/` for circuit behavior, dropped or ignored cell handling, and
  bandwidth accounting relevant to Bandguards. Cross-check the implementation
  with Tor's tests where relevant. Record the checkout revision when citing a
  finding, check it against the Tor release in the selected Docker image, and
  confirm affected behavior on that image.
- Preserve defense defaults, state continuity, and intentional exclusions.
  Review any change that can weaken protection, close legitimate circuits,
  or rotate guards unexpectedly. Make incompatible Tor settings or missing
  capabilities visible. When changing persisted state, cover existing state
  and interruption or retry as applicable. Load pickle state only from
  trusted, locally controlled sources.
- Keep passwords, cookies, keys, and production data out of fixtures and
  evidence. Redact relay fingerprints, circuit paths, and onion addresses from
  shared logs and reports. Preserve unrelated tracked, untracked, and ignored
  files. Stage only intended paths when committing. Follow task authorization
  for pushing, merging, publishing, or using live service infrastructure.

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
  the snapshot by baseline and changed files, including new files. Provide
  available validation evidence and relevant plan references.
- Assign distinct concerns when parallel review or audit work is useful.
  Give delegated implementation edits explicit file ownership and coordinate
  checks that share a checkout, Docker network, or test state. Reuse recorded
  validation unless a finding or changed input calls for a focused rerun.
  Choose reviewer coverage based on the affected contracts and avoid duplicate
  reviews of the same scope and revision.
- The coordinating agent owns findings, scope, validation, and completion. If
  independent review is unavailable, finish the checks that are possible and
  identify the review gap at handoff.

### Required reviews

- Review the design or audit scope before substantive work. Resolve material
  findings before relying on the affected decisions.
- For substantive work, independently review each implementation commit
  and each fixup at its exact SHA, including its affected consumers. For
  uncommitted work, identify the reviewed snapshot and check the resulting
  commit when created. Keep the commits, fixes, and review evidence available
  through final combined review.
- Review the combined change at meaningful integration boundaries and before
  completion. Include relevant unchanged consumers and all prior findings and
  corrections. A single review can cover a phase and an integration checkpoint
  when its scope covers both. Later changes reopen affected reviews.

### Review method

- Verify assumptions against the checkout, pinned dependencies, and effective
  Tor and Docker configuration. Challenge scope, redundant checks, and
  responsibilities that existing components can own. Compare the expected
  behavior, implementation, tests, and documentation.
- Trace affected entry points, callers, and failure paths beyond the diff.
  Check relevant authentication, guard ownership, consensus access, circuit
  actions, reload, reconnect, and state continuity. Ask what happens on both
  success and failure, including unintended effects and what the tests can
  actually establish.
- Record an independent assessment before consulting the author's rationale or
  prior findings. Then reconcile it with the plan, deviations from it, and prior
  findings and fixes. Look for repeated assumptions, cross-component hazards,
  and coverage gaps elsewhere in the affected paths. Record findings with
  evidence, the scope examined, and review limitations. Resolve material issues
  and document the disposition of proposed simplifications within scope.

## Validation

- Run focused tests first, then the affected suite. With compatible
  dependencies installed in an isolated environment, the source-tree entry
  point is `PYTHONPATH=src python3 -m pytest tests/`. Use `tox.ini` to exercise
  the installed package across the supported CPython versions. Record actual
  versions and baseline failures.
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
  observed checks, environment, and gaps. A passing mocked test establishes
  behavior for its fixture. A passing control smoke test establishes the
  exercised control operations. Qualify service or circuit behavior with
  observations at those layers. Inspect diagnostics and skips to confirm the
  intended checks actually ran.

## Local Docker integration

- Use [dockurr/tor](https://hub.docker.com/r/dockurr/tor) as the first image
  candidate. Select a supported C Tor target when planning the qualification,
  pin the chosen image by digest, and record the platform and actual
  `tor --version`. Inspect the chosen image's entrypoint, effective torrc,
  listeners, and healthcheck. The upstream entrypoint defaults its control
  listener to container loopback and generates password authentication from
  `PASSWORD`. [Image entrypoint](https://github.com/dockur/tor/blob/master/entrypoint.sh)
- Give each run a dedicated Docker project or network and disposable Tor data,
  addon config, and addon state. Pass the controller an explicit endpoint and
  use test-only authentication. Prefer a private Docker network for any
  inter-container listener. If the controller runs on the host, bind any
  published control port to host loopback and verify that the Tor listener
  inside the container is reachable through that mapping. Publish only ports
  the scenario needs.
- Check filesystem access as well as network access. The current consensus
  code reads `cached-microdesc-consensus` under the `DataDirectory` returned
  by Tor. A separate controller needs that path to resolve in its own
  filesystem and sufficient read access, or a verified replacement for the
  file-based lookup. Prefer narrowly scoped, read-only access to test data
  where sharing is necessary, with a separate writable addon state path.
- Verify readiness with authenticated control probes and, for bootstrapped
  cases, bootstrap status and the consensus input the addon needs. Use bounded
  waits and capture sanitized diagnostics on failure. Keep public-network
  bootstrap and onion-service traffic opt-in, with disposable identities and
  test traffic. Tear down run-owned containers, networks, and temporary
  volumes, including after failure.
