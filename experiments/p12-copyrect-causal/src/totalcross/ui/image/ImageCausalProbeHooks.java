// Copyright (C) 2026 Amalgam Solucoes em TI Ltda
//
// SPDX-License-Identifier: LGPL-2.1-only

package totalcross.ui.image;

import totalcross.json.JSONException;
import totalcross.json.JSONObject;

/** Experiment-only accounting access, compiled solely with the pinned custom SDK. */
public final class ImageCausalProbeHooks implements ImageDrawPathProbeAccess.CausalHooks {
  public void start() {
    ImageDrawPathProbeAccess.reset();
    Image.copyRectPhysicalOnlyForTest = 1;
  }

  public void finish() { Image.copyRectPhysicalOnlyForTest = 0; }

  public JSONObject snapshot() throws JSONException {
    JSONObject result = ImageDrawPathProbeAccess.snapshot();
    result.put("physicalOnlyEnabled", Image.copyRectPhysicalOnlyForTest != 0);
    result.put("physicalCopyAttempts", ImageRasterFeatureBridge.physicalCopyAttemptsForTest);
    result.put("physicalCopyFallbacks", ImageRasterFeatureBridge.physicalCopyFallbacksForTest);
    result.put("identityFallbacks", ImageRasterFeatureBridge.causalIdentityFallbacksForTest);
    result.put("resolveForDrawingCalls", Image.causalResolveCallsForTest);
    result.put("resolveForDrawingCacheHits", Image.causalResolveCacheHitsForTest);
    result.put("materializedVariantObservations", Image.causalVariantObservationsForTest);
    result.put("materializedVariantAdmissions", Image.causalVariantAdmissionsForTest);
    result.put("nativeGeometryMaterializations", Image.nativeGeometryMaterializationCountForTest);
    return result;
  }
}
