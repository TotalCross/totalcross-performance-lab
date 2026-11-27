# Linux startup realpath case

Reproduce I01-B on hosted Linux x86_64 with the same SDK/VM package pairing.
Record source SHA, SDK and VM hashes, runner image, glibc version, compiler
FORTIFY settings, current directory, and runtime exit code for every scenario.

Run normal, short, long, and symlink launcher paths independently. The
`realpath-compat-test-only.c` shim may be used only after recording the
unmodified result; it interposes `__realpath_chk` and does not establish that
the production VM is fixed. Expected results must include a startup marker and
an application marker so a successful shell wrapper cannot hide a VM abort.

`../../evidence/I01-B/` contains the imported PR #4 run excerpt. It is historical
evidence from source `5464c21e3107e3f1ce9c287b724829e2bb870c1d`, not the frozen
master validation.
