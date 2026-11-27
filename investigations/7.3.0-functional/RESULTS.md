# Campaign Results

No runtime investigation has been executed by this campaign yet. Initial
statuses are in `test-matrix.json` and remain `NOT_RUN` unless the matrix
identifies a verified imported historical result.

## Imported historical evidence

- **Windows Win32/I386 ownership:** PASS in TotalCross Actions run
  [45907759163](https://github.com/TotalCross/totalcross/actions/runs/45907759163).
  Historical A, historical B, and corrected source `94af2b8b653cad509994b5ccf3dbb60ac28ef920`
  started on one Windows runner. The corrected I386 runtime passed the existing
  ownership smoke. This was verified during the priority correction and is not
  a campaign execution.
- **Windows AMD64 startup:** PREEXISTING / OUT_OF_SCOPE. No campaign execution.
- JavaSE, macOS ARM64, and Android ARM64 PR #567 claims: import pending source,
  artifact, assertion, and provenance review.

No defect root cause or campaign regression is established at this checkpoint.
