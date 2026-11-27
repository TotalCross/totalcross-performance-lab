<!--
Copyright (C) 2026 Amalgam Solucoes em TI Ltda

SPDX-License-Identifier: LGPL-2.1-only
-->

# I11 — Restricted release workflow validation

## Result

**PARTIAL.** Static review, version checks, package CI evidence, and read-only
public availability probes completed. The campaign did not dispatch the
release workflow or push a tag. A real release-workflow dry-run therefore
remains unexecuted. The versioned-release-notes PR is still draft and
conflicting, and no Win32/I386-specific package result was established for
the release PR.

No tag, GitHub Release, Maven publication, Artifactory upload, or S3 upload was
created by this campaign. The product checkout was not modified.

## Source and version checks

The reviewed heads are PR #539 `b01262a8f9c096b72522d6e4d2e2448da50cbb32`
and PR #538 `b9efeff51e5515121684a2a00db7bdbdd3aacee6`. Both remain open and
draft; #539 currently conflicts with its base. The release workflow file is
byte-identical at both heads (SHA-256
`7809edce725e86534896120219d603e8691f1b30ca74a781f6fcbf78e65d3e3f`).

Version values agree across the release inputs:

| Source | Value |
| --- | --- |
| `TotalCrossSDK/build.gradle` | `7.3.0` |
| `Settings.version` | `730` |
| `Settings.versionStr` | `7.3.0` |
| `TotalCrossVM/CMakeLists.txt` | `7.3.0` |
| `docs/releases/7.3.0.md` heading | `# TotalCross 7.3.0` |

The release workflow requires the matching notes file to exist, be nonempty,
and contain that exact heading before staging it as release notes.

The notes state that Google Play requires API 36 for new apps and updates
submitted after August 31, 2026. Google's current policy page confirms that
requirement. The notes also state that App Store uploads require Xcode 26 with
the iOS 26 SDK or later and an iOS 13-or-later deployment target. Apple's
current requirements page confirms those dates and minimums as of this review.
[Google Play target API requirements](https://support.google.com/googleplay/android-developer/answer/11926878?hl=en-en)
and [Apple's upcoming requirements](https://developer.apple.com/news/upcoming-requirements/)
are the sources used for these time-sensitive claims.

## Package and platform evidence

The canonical `package.yml` run at the #538 head was successful:

- The #538 `Merge flow` check run
  [43979197934](https://github.com/TotalCross/totalcross/actions/runs/43979197934)
  passed the SDK build, Linux x86/64 native build, and macOS ARM64 native
  build.
- Run [44003872364](https://github.com/TotalCross/totalcross/actions/runs/44003872364)
  packaged the 7.3.0 distribution (artifact `TotalCross-7.3.0`, ID
  `14294016698`, 109,260,329 bytes, Actions digest
  `sha256:26817d29624082a1cc426306f783a319a1cc04700d81a3638095e1e85c55b83c`).
- The SDK build, packaged ZIP inventory/provenance step, Linux x86/64 ZIP test,
  and macOS ARM ZIP test completed successfully. The exact job IDs and artifact
  metadata are in [the I11 evidence index](../evidence/I11/index.json).
- This CI record does not establish that its Windows package is Win32/I386.
  The I11 campaign did not inspect or rely on a Windows AMD64 result. The
  separately verified Win32/I386 compatibility run is recorded under I10 and
  in [the Windows ownership report](I06-windows-win32-ownership.md).

The existing official 7.3.0 package artifact from run
[40878222908](https://github.com/TotalCross/totalcross/actions/runs/40878222908)
was also used by the campaign's I10 matrix. It is a `package.yml` run, not an
execution of the release workflow. Its source and artifact digests remain in
`provenance.json` and I10 evidence.

## Release workflow guards

The reviewed workflow parses as YAML. Its public publication steps are guarded
by `DRY_RUN != 'true'`; the Maven Central and legacy Artifactory uploads also
require their respective opt-in inputs. For a manual dispatch, `dry_run`
defaults to true, and only an explicit false value selects live mode. A
matching `v*` tag push sets `DRY_RUN` to false automatically. That path can
upload to S3 and create a GitHub Release even when both Maven switches remain
false.

The manual dry-run is not free of workflow-side effects or sensitive access:
the job requests `contents: write` and `id-token: write`, uses the
`maven-central` environment, imports the GPG signing key, prepares the signed
Maven Central bundle, and uploads prepared files as Actions artifacts. The
campaign therefore made no dispatch and no tag push. Static inspection found
the configured public publication gates; it did not exercise those gates in a
workflow run.

## Read-only public availability probes

On 2026-11-27, direct endpoint checks found no `v7.3.0` GitHub tag or release,
no matching Maven Central search result, HTTP 404 for the Maven Central POM,
HTTP 404 for the release ZIP URL, and HTTP 404 for the checked legacy
Artifactory POM URL. These are point-in-time checks of the listed identifiers
and endpoints, not proof that every possible mirror or coordinate is empty.
The exact URLs and observed HTTP statuses are in
[`public-availability-probes.json`](../evidence/I11/public-availability-probes.json).

## Historical ownership claims

PR #567's description claims focused JavaSE tests plus macOS ARM64 and Android
ARM64 smoke results, but does not link durable run or artifact IDs for those
claims. Its accessible PR check run has a successful SDK build; the platform
native jobs were skipped. The referenced
`codex/image-ownership-cross-platform-smoke` branch has no Actions run in the
accessible performance-lab repository. These historical claims were therefore
not imported as independently verified I06 evidence. The campaign's own
Windows Win32/I386 and conditional Linux ownership results, plus its separate
macOS and Android I07 runtime evidence, remain independently recorded.

## Validation performed

- Parsed the PR #538/#539 release workflow and canonical package workflow as
  YAML.
- Checked the package helper shell scripts with `bash -n`.
- Compared the four version inputs and release-note heading.
- Reviewed package workflow job conclusions, artifact inventory metadata,
  release publication conditions, and public URLs without dispatching the
  release workflow.
- No production build, release workflow run, tag, publication, or PR action was
  performed for I11.
