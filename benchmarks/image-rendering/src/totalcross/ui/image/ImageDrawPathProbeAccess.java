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

  /** Supplied only by the experiment-local entry class; normal SDK builds need no experimental fields. */
  public interface CausalHooks {
    void start();
    void finish();
    JSONObject snapshot() throws JSONException;
  }

  public interface AdmissionMemoryHooks {
    void start(Image[] images, String policy);
    void paint(int index);
    JSONObject frame() throws JSONException;
    JSONObject finish(Image[] images) throws JSONException;
  }
  private static AdmissionMemoryHooks admissionMemoryHooks;
  public static void installAdmissionMemoryHooks(AdmissionMemoryHooks hooks) {admissionMemoryHooks=hooks;}
  public static void startAdmissionMemory(Image[] images,String policy) {
    if(admissionMemoryHooks==null)throw new IllegalStateException("memory probe needs its isolated package");
    admissionMemoryHooks.start(images,policy);
  }
  public static void admissionMemoryPaint(int index) {if(admissionMemoryHooks!=null)admissionMemoryHooks.paint(index);}
  public static JSONObject admissionMemoryFrame() throws JSONException {return admissionMemoryHooks.frame();}
  public static JSONObject finishAdmissionMemory(Image[] images) throws JSONException {return admissionMemoryHooks.finish(images);}

  private static CausalHooks causalHooks;

  public static void installCausalHooks(CausalHooks hooks) {
    causalHooks = hooks;
  }

  public static void startCausalExperiment() {
    if (causalHooks == null) throw new IllegalStateException("causal probe needs its experimental package");
    causalHooks.start();
  }

  public static void finishCausalExperiment() {
    causalHooks.finish();
  }

  public static JSONObject causalSnapshot() throws JSONException {
    return causalHooks.snapshot();
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

  public static String statusHex(int status) {
    // Integer4D.toHexString truncates to four uppercase digits on the native VM.
    String digits = "0123456789abcdef";
    String hex = "";
    do {
      hex = digits.charAt(status & 15) + hex;
      status >>>= 4;
    } while (status != 0);
    return "0x" + hex;
  }

  public static JSONArray classify(JSONObject counters) throws JSONException {
    JSONObject flags = decodeStatus(counters.getInt("copyRectPlanLastStatus"));
    JSONArray tags = new JSONArray();
    add(tags, counters.getInt("cachedFinalRasterHits") > 0, "cached-final hit");
    add(tags, counters.getInt("cachedFinalRasterMisses") > 0, "cached-final miss");
    // Native status records identity outcomes even when Image's getters stay zero.
    add(tags, flags.getBoolean("identityAttempted") || counters.getInt("identityAttempts") > 0, "identity attempted");
    add(tags, flags.getBoolean("identityHit") || counters.getInt("identityHits") > 0, "identity hit");
    add(tags, flags.getBoolean("identityFallback") || counters.getInt("identityFallbacks") > 0, "identity fallback");
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

  public static JSONObject mappingMetadata(Image image, totalcross.ui.gfx.Graphics graphics) throws Exception {
    ImageDrawPlan plan = (ImageDrawPlan) image.drawPlanForDrawing(graphics.getContentScale());
    if (plan == null || plan.root.backing == null) {
      throw new IllegalStateException("physical mapping probe requires a normal native draw plan");
    }
    ImageBacking backing = plan.root.backing;
    long backingGeneration = backing.mutationGeneration();
    // The Image generation accessor synchronizes a private field. Its raw
    // value is unavailable to read-only inspection; do not infer it from backing.
    JSONObject result = new JSONObject();
    result.put("operationCount", plan.operations.length);
    result.put("operations", integers(plan.operations));
    result.put("parameters", integers(plan.parameters));
    result.put("dimensions", integers(plan.dimensions));
    result.put("rootWidth", plan.rootWidth);
    result.put("rootHeight", plan.rootHeight);
    result.put("rootLogicalWidth", plan.rootLogicalWidth);
    result.put("rootLogicalHeight", plan.rootLogicalHeight);
    result.put("rootFrameCount", plan.rootFrameCount);
    result.put("rootWidthOfAllFrames", plan.rootWidthOfAllFrames);
    result.put("currentFrame", plan.currentFrame);
    result.put("rootContentScale", plan.rootContentScale);
    result.put("rootHwScaleW", plan.rootHwScaleW);
    result.put("rootHwScaleH", plan.rootHwScaleH);
    result.put("outputWidth", plan.outputWidth);
    result.put("outputHeight", plan.outputHeight);
    result.put("destinationScale", plan.destinationScale);
    result.put("outputContentScale", plan.outputContentScale);
    result.put("hwScaleW", plan.hwScaleW);
    result.put("hwScaleH", plan.hwScaleH);
    result.put("alphaMask", plan.alphaMask);
    result.put("materializeAlphaMask", plan.materializeAlphaMask);
    result.put("outputAlphaMask", plan.outputAlphaMask);
    result.put("backingType", backing.getClass().getName());
    result.put("backingNative", backing.isNative());
    result.put("backingValid", backing.isValid());
    result.put("backingWidth", backing.width());
    result.put("backingHeight", backing.height());
    result.put("sourceBackingStable", backing.backingIdentityStableForCaching());
    result.put("sourceMutationGeneration", JSONObject.NULL);
    result.put("sourceMutationGenerationAvailable", false);
    result.put("backingMutationGeneration", backingGeneration);
    result.put("sourceOpacityState", backing.opacityState());
    result.put("graphicsContentScale", graphics.getContentScale());
    result.put("drawableWidth", graphics.getSurfacePixelWidth());
    result.put("drawableHeight", graphics.getSurfacePixelHeight());
    totalcross.ui.gfx.Coord translation = graphics.getTranslation();
    totalcross.ui.gfx.Rect clip = graphics.getClip(new totalcross.ui.gfx.Rect());
    result.put("graphicsTranslationX", translation.x);
    result.put("graphicsTranslationY", translation.y);
    result.put("clipX", clip.x);
    result.put("clipY", clip.y);
    result.put("clipWidth", clip.width);
    result.put("clipHeight", clip.height);
    if (plan.root.backing != backing || backing.mutationGeneration() != backingGeneration) {
      throw new IllegalStateException("mapping inspection observed changed backing identity/generation");
    }
    result.put("inspectionObservableStateUnchanged", true);
    return result;
  }

  private static JSONArray integers(int[] values) {
    JSONArray result = new JSONArray();
    for (int value : values) {
      result.put(value);
    }
    return result;
  }

  private static void add(JSONArray tags, boolean present, String tag) {
    if (present) tags.put(tag);
  }
}
