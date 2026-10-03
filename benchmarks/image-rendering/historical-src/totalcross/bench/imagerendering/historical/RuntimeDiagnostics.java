// Copyright (C) 2026 Amalgam Solucoes em TI Ltda
//
// SPDX-License-Identifier: LGPL-2.1-only

package totalcross.bench.imagerendering.historical;

/** Compile-only adapter: f5dad132 has no public RuntimeDiagnostics API. */
public final class RuntimeDiagnostics {
  private RuntimeDiagnostics() { }
  public static boolean isSupported() { return false; }
  public static RuntimeDiagnosticSnapshot snapshot() {
    throw new UnsupportedOperationException("historical runtime diagnostics are unavailable");
  }
  public static void setDomainEnabled(RuntimeDiagnosticSnapshot.Domain domain, boolean enabled) {
    throw new UnsupportedOperationException("historical runtime diagnostics are unavailable");
  }
}
