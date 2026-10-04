<!--
Copyright (C) 2026 Amalgam Solucoes em TI Ltda

SPDX-License-Identifier: LGPL-2.1-only
-->
# Compare immediate materialized admission

ExecPlan follows the unchanged TotalCross AGENTS.md and .agent/PLANS.md,
read in full during the preceding experiment.

## Purpose / Big Picture
Measure only first-successful-materialization admission versus second-observation
admission on the validated causal copyRect routing. One untimed stabilization,
exactly five timed tree samples, no production policy decision or residual-gap study.

## Working Set and Resume Protocol
Read this plan first. Runtime .local-data/runtime-immediate-admission is based on
fc08c39499dead73b327ad259a992ab34ec42870. This directory's admission.patch records
the precise delta; runtime.patch records the full reproducible patch from 5a44f503.
provenance.json indexes exact source/build/package/first-process paths and hashes.
The experiment-local Java hooks/entry select admission; shared causal workload
retains counters and measurement protocol. tools/copyrect_causal.py and packaging
select exact experiment identities. reports/p12-immediate-admission-probe.md holds
final interpretation. Raw output and normal artifacts stay local, never committed.

## Progress
- [x] Prior measured routing and current scale/generation/backing checks inspected.
- [x] Narrow hook, SDK failure/default/cache-validity tests and lab protocol contracts.
- [x] Source/tooling committed; exact SDK/tcvm/Launcher packaged and hashes verified.
- [x] Sole runner/application exited 0/0; complete record analyzed and reported.
- [x] Final offline validation passed; report/checkpoint/provenance publication checkpoint.

## Current Architecture and Scope
Image.resolveForDrawing validates destination scale, probes the existing exact
cached variant, materializes/synchronizes successfully and recomputes the source
generation before observing/admitting. At that admission decision only, an
experiment-only field may bypass the second-observation gate. It additionally
requires physical-only routing and explicit test accounting. All fields are zero
by default; the isolated entry enables the new field immediately before the
explicit stabilization and resets it afterwards. Cache lookup/store, validity,
ImagePipeline and every native source remain unchanged relative to fc08c394.

## Plan of Work
Test first eligible successful admission, failed materialization/invalid scales,
exact-scale/generation/invalid-backing rejection, disabled guards and baseline
second-observation behavior. Validate complete protocol even for surprising
results. Build/package one current custom source; commit before measurement.
Verify source cleanliness, artifacts, dataset, authorization freshness, then one
inline-preflight process. Analyze all five samples with prior fixed references.

## Decision Log
A second test-only field is narrower than modifying ImagePipeline admission or
introducing a public policy/API. Keep the prior routing and shared protocol exact.
No native source change is needed, but all artifacts are rebuilt from this source
revision so runtime/SDK identity remains consistent. No historical/alternate run.

## Validation and Acceptance
Focused SDK/JUnit admission and existing destination-scale/backing/decode tests,
focused native routing test, all lab Python tests, header checks, normal-official
and custom Java compilation, Release ARM64 build/package and hash verification.
Exactly one valid native application process with six counter snapshots and five
measured times. No acceptance gate assumes cached hits or a timing outcome.
Expensive unrelated matrix/platform/sanitizer validation is deferred because this
is an isolated admission experiment, not a production release or cache decision.

## Risks and Open Questions
An admitted variant might fail later generation/scale/backing validation; counters
must preserve surprising results. Two non-deferred resolve calls existed in the
prior tree and should be distinguished from image materializations. The residual
~3.57 versus ~1.02 ms gap is explicitly out of scope.

## Idempotence and Recovery
Create an exclusive local marker before launch. After any valid sample, never
replace/relaunch. Preserve a pre-sample tooling failure and fix offline first;
no silent retry. Leave previous artifacts/processes and production branches intact.

## Outcomes & Retrospective
All 18 stabilization admissions were immediately reusable; all five samples were
cached-final hits (median 3.650708 ms). Production policy and historical residual
remain unresolved. See dedicated report and indexed original evidence.
