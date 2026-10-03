// Copyright (C) 2026 Amalgam Solucoes em TI Ltda
//
// SPDX-License-Identifier: LGPL-2.1-only

package totalcross.ui.image;

import totalcross.json.JSONException;
import totalcross.json.JSONObject;

/** Adds only immediate admission to the unchanged causal-routing hooks. */
public final class ImageImmediateAdmissionHooks implements ImageDrawPathProbeAccess.CausalHooks {
  private final ImageCausalProbeHooks routing = new ImageCausalProbeHooks();

  public void start() {
    routing.start();
    Image.immediateMaterializedAdmissionForTest = 1;
  }

  public void finish() {
    Image.immediateMaterializedAdmissionForTest = 0;
    routing.finish();
  }

  public JSONObject snapshot() throws JSONException {
    JSONObject result = routing.snapshot();
    result.put("immediateAdmissionEnabled", Image.immediateMaterializedAdmissionForTest != 0);
    return result;
  }
}
