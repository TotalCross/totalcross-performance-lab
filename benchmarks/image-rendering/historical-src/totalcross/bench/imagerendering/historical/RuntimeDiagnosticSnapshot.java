// Copyright (C) 2026 Amalgam Solucoes em TI Ltda
//
// SPDX-License-Identifier: LGPL-2.1-only

package totalcross.bench.imagerendering.historical;

/** Types for unreachable diagnostic branches of the shared workload. */
public final class RuntimeDiagnosticSnapshot {
  public enum Domain { IMAGE, PREFETCH }
  public enum Kind { COUNTER, TIMER, GAUGE }
  private RuntimeDiagnosticSnapshot() { }
  public RuntimeDiagnosticSnapshot deltaSince(RuntimeDiagnosticSnapshot other) {
    throw new UnsupportedOperationException("historical runtime diagnostics are unavailable");
  }
  public long getValue(Domain domain, Kind kind) {
    throw new UnsupportedOperationException("historical runtime diagnostics are unavailable");
  }
}
