# ImageDrawingBridge ownership probe

`tests/functional-validation/totalcross/ui/image/ImageOwnershipLifecycleProbe.java`
is the persistent ownership lifecycle probe imported from performance-lab
commit `bf691c14d7c5fe807c62de98c7285f65d38de87e`, path
`tests/image-ownership/src/totalcross/ui/image/ImageOwnershipLifecycleProbe.java`.
The source retains its MIT SPDX marker. It exercises baseline diagnostic and
corrected acceptance modes against exact SDK builds and a Linux native runtime.

The Linux runtime runs on Ubuntu 22.04; the separate glibc 2.39 startup blocker
is tracked under I01-B. Runner and runtime output are recorded under
`evidence/I06/`. Baseline ownership mismatches are observations, not a pass
condition. The corrected candidate must complete all seven stages, report zero
mismatches, satisfy each ownership assertion, render the expected red pixel,
and exit successfully.
