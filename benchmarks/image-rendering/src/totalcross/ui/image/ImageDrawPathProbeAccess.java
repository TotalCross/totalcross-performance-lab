// Copyright (C) 2026 Amalgam Solucoes em TI Ltda
//
// SPDX-License-Identifier: LGPL-2.1-only

package totalcross.ui.image;

import totalcross.json.JSONArray;
import totalcross.json.JSONException;
import totalcross.json.JSONObject;

/** Benchmark-only access to existing SDK test accounting; never part of the SDK. */
public final class ImageDrawPathProbeAccess {
  private ImageDrawPathProbeAccess() { }

  public static void reset() {
    ImageRasterFeatureBridge.resetDrawAccountingForTest();
    Image.resetImageOperationAccountingForTest();
  }

  public static JSONObject snapshot() throws JSONException {
    JSONObject result = new JSONObject();
    result.put("copyRectPlanAttempts", ImageRasterFeatureBridge.copyRectPlanAttemptsForTest);
    result.put("copyRectPlanHandled", ImageRasterFeatureBridge.copyRectPlanHandledForTest);
    result.put("copyRectPlanFallbacks", ImageRasterFeatureBridge.copyRectPlanFallbacksForTest);
    result.put("copyRectPlanLastStatus", ImageRasterFeatureBridge.copyRectPlanLastStatusForTest);
    result.put("cachedFinalRasterProbes", ImageRasterFeatureBridge.cachedFinalRasterProbesForTest);
    result.put("cachedFinalRasterHits", ImageRasterFeatureBridge.cachedFinalRasterHitsForTest);
    result.put("cachedFinalRasterMisses", ImageRasterFeatureBridge.cachedFinalRasterMissesForTest);
    result.put("identityAttempts", ImageRasterFeatureBridge.identityAttemptsForTest);
    result.put("identityHits", Image.physicalIdentityHitCountForTest());
    result.put("identityFallbacks", Image.physicalIdentityFallbackCountForTest());
    result.put("physicalCopyHits", ImageRasterFeatureBridge.physicalCopyHitsForTest);
    result.put("genericGeometryDraws", ImageRasterFeatureBridge.genericGeometryDrawsForTest);
    result.put("smoothResampleDraws", ImageRasterFeatureBridge.smoothResampleDrawsForTest);
    result.put("directDrawPlanExecutions", Image.directDrawPlanExecutionCountForTest());
    result.put("targetColorHits", ImageRasterFeatureBridge.targetColorVariantHitsForTest);
    result.put("targetColorMaterializations", ImageRasterFeatureBridge.targetColorVariantMaterializationsForTest);
    result.put("targetColorFallbacks", ImageRasterFeatureBridge.targetColorVariantFallbacksForTest);
    result.put("physicalVariantHits", Image.physicalVariantHitCountForTest());
    result.put("physicalVariantMaterializations", Image.physicalVariantMaterializationCountForTest());
    result.put("physicalVariantFallbacks", Image.physicalVariantFallbackCountForTest());
    return result;
  }

  public static JSONObject decodeStatus(int status) throws JSONException {
    JSONObject result = new JSONObject();
    result.put("handled", (status & ImageRasterDiagnostics.DRAW_HANDLED) != 0);
    result.put("identityAttempted", (status & ImageRasterDiagnostics.DRAW_IDENTITY_ATTEMPT) != 0);
    result.put("identityHit", (status & ImageRasterDiagnostics.DRAW_IDENTITY_HIT) != 0);
    result.put("identityFallback", (status & ImageRasterDiagnostics.DRAW_IDENTITY_FALLBACK) != 0);
    result.put("physicalCopyHit", (status & ImageRasterDiagnostics.DRAW_PHYSICAL_COPY_HIT) != 0);
    result.put("targetColorAttempted", (status & ImageRasterDiagnostics.DRAW_TARGET_COLOR_ATTEMPT) != 0);
    result.put("targetColorHit", (status & ImageRasterDiagnostics.DRAW_TARGET_COLOR_HIT) != 0);
    result.put("targetColorMaterialized", (status & ImageRasterDiagnostics.DRAW_TARGET_COLOR_MATERIALIZED) != 0);
    result.put("targetColorFallback", (status & ImageRasterDiagnostics.DRAW_TARGET_COLOR_FALLBACK) != 0);
    result.put("physicalVariantAttempted", (status & ImageRasterDiagnostics.DRAW_PHYSICAL_VARIANT_ATTEMPT) != 0);
    result.put("physicalVariantHit", (status & ImageRasterDiagnostics.DRAW_PHYSICAL_VARIANT_HIT) != 0);
    result.put("physicalVariantMaterialized", (status & ImageRasterDiagnostics.DRAW_PHYSICAL_VARIANT_MATERIALIZED) != 0);
    result.put("physicalVariantFallback", (status & ImageRasterDiagnostics.DRAW_PHYSICAL_VARIANT_FALLBACK) != 0);
    result.put("genericGeometry", (status & ImageRasterDiagnostics.DRAW_GENERIC_GEOMETRY) != 0);
    result.put("smoothResample", (status & ImageRasterDiagnostics.DRAW_SMOOTH_RESAMPLE) != 0);
    return result;
  }

  public static JSONArray classify(JSONObject counters) throws JSONException {
    JSONObject flags = decodeStatus(counters.getInt("copyRectPlanLastStatus"));
    JSONArray tags = new JSONArray();
    add(tags, counters.getInt("cachedFinalRasterHits") > 0, "cached-final hit");
    add(tags, counters.getInt("cachedFinalRasterMisses") > 0, "cached-final miss");
    add(tags, counters.getInt("identityAttempts") > 0, "identity attempted");
    add(tags, counters.getInt("identityHits") > 0, "identity hit");
    add(tags, counters.getInt("identityFallbacks") > 0, "identity fallback");
    tags.put(counters.getInt("physicalCopyHits") > 0 ? "physical-copy hit" : "physical-copy no hit");
    for (String path : new String[] {"targetColor", "physicalVariant"}) {
      String label = "targetColor".equals(path) ? "target-color" : "physical-variant";
      add(tags, flags.getBoolean(path + "Attempted"), label + " attempted");
      add(tags, flags.getBoolean(path + "Hit") || counters.getInt(path + "Hits") > 0, label + " hit");
      add(tags, flags.getBoolean(path + "Materialized") || counters.getInt(path + "Materializations") > 0,
          label + " materialized");
      add(tags, flags.getBoolean(path + "Fallback") || counters.getInt(path + "Fallbacks") > 0, label + " fallback");
    }
    add(tags, counters.getInt("genericGeometryDraws") > 0, "generic geometry");
    add(tags, counters.getInt("smoothResampleDraws") > 0, "smooth resample");
    add(tags, counters.getInt("copyRectPlanHandled") > 0, "draw handled");
    add(tags, counters.getInt("copyRectPlanFallbacks") > 0, "draw fallback");
    add(tags, counters.getInt("copyRectPlanAttempts") == 0, "no copyRect plan attempt");
    return tags;
  }

  public static boolean unexpectedDisabledPathActivity(JSONObject counters) throws JSONException {
    JSONObject flags = decodeStatus(counters.getInt("copyRectPlanLastStatus"));
    for (String path : new String[] {"targetColor", "physicalVariant"}) {
      if (flags.getBoolean(path + "Attempted") || flags.getBoolean(path + "Hit")
          || flags.getBoolean(path + "Materialized") || flags.getBoolean(path + "Fallback")
          || counters.getInt(path + "Hits") > 0 || counters.getInt(path + "Materializations") > 0
          || counters.getInt(path + "Fallbacks") > 0) {
        return true;
      }
    }
    return false;
  }

  private static void add(JSONArray tags, boolean present, String tag) {
    if (present) tags.put(tag);
  }
}
