// Copyright (C) 2026 Amalgam Solucoes em TI Ltda
//
// SPDX-License-Identifier: LGPL-2.1-only

package totalcross.bench.imagerendering;

/** Timing constants and interpolation for the isolated historical scroll probe. */
final class ScrollTiming {
  static final long HISTORICAL_DURATION_NS = 3000000000L;
  static final long HISTORICAL_CADENCE_NS = 16000000L;

  private ScrollTiming() { }

  static int historicalTarget(int minimum, int endpoint, long elapsedNs) {
    if (endpoint < minimum) {
      throw new IllegalArgumentException("scroll endpoint precedes its minimum");
    }
    if (elapsedNs <= 0L) {
      return minimum;
    }
    if (elapsedNs >= HISTORICAL_DURATION_NS) {
      return endpoint;
    }
    long range = (long) endpoint - minimum;
    long whole = range / HISTORICAL_DURATION_NS;
    long remainder = range % HISTORICAL_DURATION_NS;
    long target = minimum + whole * elapsedNs
        + remainder * elapsedNs / HISTORICAL_DURATION_NS;
    if (target < minimum) {
      return minimum;
    }
    if (target > endpoint) {
      return endpoint;
    }
    return (int) target;
  }

  static int boundedSleepMillis(long remainingNs) {
    if (remainingNs <= 0L) {
      return 1;
    }
    long millis = (remainingNs + 999999L) / 1000000L;
    return (int) Math.min(4L, Math.max(1L, millis));
  }
}
