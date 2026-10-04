# Schemas

Machine-readable dataset, benchmark configuration, result, and environment contracts live here.

Schemas should be versioned explicitly and should avoid embedding run-specific paths or transient machine state. Image-rendering run records, summaries, host provenance, and generated Windows package manifests use the v1 schemas in this directory. Durations in run records are integer nanoseconds; reports convert them to milliseconds.
