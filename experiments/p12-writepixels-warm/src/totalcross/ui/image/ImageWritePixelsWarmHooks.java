// Copyright (C) 2026 Amalgam Solucoes em TI Ltda
//
// SPDX-License-Identifier: LGPL-2.1-only

package totalcross.ui.image;

import totalcross.json.JSONArray;
import totalcross.json.JSONException;
import totalcross.json.JSONObject;
import totalcross.sys.Convert;

/** Isolated bit-2-equivalent native hook composed over unchanged prior hooks. */
public final class ImageWritePixelsWarmHooks implements ImageDrawPathProbeAccess.CausalHooks {
  private final ImageImmediateAdmissionHooks admission = new ImageImmediateAdmissionHooks();
  private static long metric(int id, int field) { return NativeImageBacking.metricForTest(id, field); }
  private static long value(int row, int field) { return metric(105, row * 37 + field); }

  public void start() {
    admission.start();
    if (metric(101, 0) != 0) throw new IllegalStateException("writePixels experiment was already enabled");
    if (metric(100, 1) != 1) throw new IllegalStateException("writePixels experiment could not enable");
  }
  public void finish() { metric(100, 0); admission.finish(); }

  private static JSONArray rectangle(int row, int field, boolean floats) throws JSONException {
    JSONArray a = new JSONArray();
    for (int i=0; i<4; i++) {
      long v=value(row, field+i);
      if (floats) a.put(Convert.intBitsToDouble((int)v)); else a.put((int)v);
    }
    return a;
  }

  public JSONObject snapshot() throws JSONException {
    JSONObject result=admission.snapshot();
    JSONObject wp=new JSONObject();
    wp.put("enabled", metric(101, 0) == 1);
    String[] names={"attempts","hits","fallbacks","copiedBytes","clippedHits","opacityScans",
        "opacityScanPixels","attemptNs","writeNs","fallbackNs","fallbackDraws"};
    for(int i=0;i<names.length;i++) wp.put(names[i],metric(102,i));
    String[] reasons={"none","invalidTargetOrSource","alphaMask","sourceRect","matrix",
        "fractionalDestination","sizeMismatch","destinationBounds","opacity",
        "unsupportedFormat","sourcePixels","writeFailure"};
    JSONObject rejected=new JSONObject();
    for(int i=1;i<reasons.length;i++) rejected.put(reasons[i],metric(104,i));
    wp.put("rejections",rejected);
    JSONArray draws=new JSONArray();
    int count=(int)metric(103,0);
    for(int row=0;row<count;row++) {
      JSONObject d=new JSONObject();
      d.put("sourceHandle",value(row,0)); d.put("sourceFormat",value(row,1));
      d.put("sourceWidth",value(row,2));d.put("sourceHeight",value(row,3));
      d.put("opacityBefore",value(row,4));d.put("opacityAfter",value(row,5));
      d.put("hit",value(row,6)==1); int reason=(int)value(row,7);
      d.put("rejection",reasons[reason]);d.put("copiedBytes",value(row,8));
      d.put("clipped",value(row,9)==1);
      d.put("sourcePhysical",rectangle(row,10,true));
      d.put("destinationLogical",rectangle(row,14,true));
      d.put("destinationDevice",rectangle(row,18,true));
      boolean planned=reason==0||reason>=8;
      d.put("clippedSourcePhysical",planned?rectangle(row,22,false):JSONObject.NULL);
      d.put("clippedDestinationDevice",planned?rectangle(row,26,false):JSONObject.NULL);
      d.put("canvasScaleTranslation",rectangle(row,30,true));
      d.put("attemptNs",value(row,34));d.put("writeNs",value(row,35));d.put("fallbackNs",value(row,36));
      draws.put(d);
    }
    wp.put("draws",draws);result.put("writePixels",wp);return result;
  }
}
