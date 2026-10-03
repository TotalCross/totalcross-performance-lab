<!--
Copyright (C) 2026 Amalgam Solucoes em TI Ltda

SPDX-License-Identifier: LGPL-2.1-only
-->
# Test copyRect fallback causally

This ExecPlan follows TotalCross AGENTS.md and .agent/PLANS.md (read in full).

## Purpose / Big Picture
Test whether handling generic smooth geometry in copyRect prevents final-raster
materialization and reuse. Preserve second-observation admission. One stabilization
repaint, exactly five whole-tree samples, retained top viewport 6 rows/18 Images.

## Working Set and Resume Protocol
Read this plan first. Experiment runtime worktree: .local-data/runtime-copyrect-causal,
based on clean 5a44f503. Canonical runtime change is runtime.patch in this directory.
Experiment-local hooks/default entry plus benchmark helper/ScrollWorkload, runners/run.py, tools/copyrect_causal.py and focused
tests implement instrumentation/protocol. Local .local-data/copyrect-causal/evidence.json
indexes builds and sole launch; logs/results are local and never committed. Dedicated
reports/p12-copyrect-causal-probe.md supplies the final interpretation.

## Progress
- [x] Current routing, native predicates and admission implementation inspected.
- [x] Runtime switch/counters and isolated hooks implemented; 90 Python tests, native routing tests, header checks and both SDK compilations passed.
- [ ] Commit implementation, build consistent custom SDK/native artifacts and verify hashes.
- [ ] Sole runtime process, five-sample analysis, documentation commit and push.

## Current Architecture and Scope
Production copyRect probes existing cached-final state before draw-plan execution.
Native physical rejection continues to generic smooth geometry and returns HANDLED.
The experiment adds a test-only field, false until the explicit probe stabilization.
Native copyRect checks it, tries unchanged physical/identity eligibility and returns
unhandled on rejection before target-color/physical-variant/generic drawing. Existing
Java fallback then calls resolveForDrawing; cache admission code stays byte-identical.
Test counters observe resolve calls, cache hits, observations/admissions and direct
native draw/copy paths. The default SDK/renderer/optimization masks stay unchanged.

## Plan of Work
Implement the narrowly enabled experimental branch and counters. Validate both
switch states, physical hits/fallback and exact five-sample protocol offline. Commit
runtime branch and preserve its patch in the lab. Build only macOS arm64 Release
SDK/tcvm/Launcher and focused native tests from that exact runtime commit. Package
only default, using one consistent source revision. Verify clean sources and hashes,
then launch the one-process inline-preflight driver once. Analyze without rerunning.

## Decision Log
Use an isolated custom runtime; the official binary cannot enforce physical-only
routing. Enable the field only immediately before stabilization so startup paints
remain production behavior. Never replace admission or physical mapping semantics.
A surprising valid sequence is evidence, not authorization for another launch.

## Validation and Acceptance
Focused native routing tests, SDK test-only counter validation, Python protocol/schema
fixtures and unittest discovery; compile/package and provenance checks before launch.
One untimed stabilization plus five whole-tree samples; all counts, retained identities,
position, unchanged typed runtime defaults and axes verified. Explicit runner/native exits and artifact hashes.
Expensive unrelated platform/matrix/sanitizer validation is deferred: causal experiment,
not a production architecture or release gate.

## Risks and Open Questions
Startup/resolve prefix activity might affect admission; capture the stabilization
counters instead of assuming it is observation one. Collect all five samples even
if the expected expensive/fast sequence fails. No timing-based parser acceptance.

## Idempotence and Recovery
An exclusive local launch marker consumes this authorization. Never launch again
after any valid sample. Preserve first evidence and analyze offline after failures.
No build/cache cleanup or unrelated source edits. Do not merge any PR.

## Outcomes & Retrospective
Pending measurement. Immediate-vs-second-observation admission remains unresolved.
