// Copyright (C) 2026 Amalgam Solucoes em TI Ltda
//
// SPDX-License-Identifier: LGPL-2.1-only
package totalcross.ui.image;
import totalcross.json.*;

/** Primitive-only accounting over unchanged one-slot ownership; never holds Images. */
public final class ImageAdmissionMemoryHooks implements ImageDrawPathProbeAccess.AdmissionMemoryHooks {
  private final ImageCausalProbeHooks causal=new ImageCausalProbeHooks();
  private static long metric(int id,int field) {return NativeImageBacking.metricForTest(id,field);}
  public void start(Image[] images,String policy) {
    if(!"IMMEDIATE".equals(policy)&&!"SECOND_OBSERVATION".equals(policy))throw new IllegalArgumentException("policy");
    for(Image image:images)if(image.pipelineForSmoke()==null||image.pipelineForSmoke().cachedVariantCountForSmoke()!=0)
      throw new IllegalStateException("initial pipeline already has a final raster");
    causal.start();
    Image.immediateMaterializedAdmissionForTest="IMMEDIATE".equals(policy)?1:0;
    AdmissionMemoryForTest.start(images.length);
    for(int i=0;i<images.length;i++) {images[i].pipelineForSmoke().admissionProbeIndexForTest=i;AdmissionMemoryForTest.source(images[i].pipelineForSmoke());}
    if(metric(101,0)!=0||metric(100,1)!=1)throw new IllegalStateException("writePixels enable");
    metric(108,1);
  }
  public void paint(int index) {if(AdmissionMemoryForTest.enabled)AdmissionMemoryForTest.paints[index]++;}
  private JSONObject category(int category) throws JSONException {
    JSONObject o=new JSONObject();String[] names={"liveCount","peakCount","liveBytes","peakBytes","releasedCount","taggedCount","allocatedBytes"};
    for(int i=0;i<names.length;i++)o.put(names[i],metric(203,category*8+i));return o;
  }
  public JSONObject frame() throws JSONException {
    JSONObject o=new JSONObject();
    o.put("cacheLiveCount",AdmissionMemoryForTest.liveCount);o.put("cachePeakCount",AdmissionMemoryForTest.peakCount);
    o.put("cacheLiveBytes",AdmissionMemoryForTest.liveBytes);o.put("cachePeakBytes",AdmissionMemoryForTest.peakBytes);
    o.put("materializations",AdmissionMemoryForTest.materializations);o.put("materializationNs",AdmissionMemoryForTest.materializationNs);
    o.put("allocatedFinalBytes",AdmissionMemoryForTest.allocatedBytes);o.put("admissions",AdmissionMemoryForTest.installs);
    o.put("nativeLiveCount",NativeImageBacking.backingRecordsLiveForTest());o.put("nativePeakCount",NativeImageBacking.backingRecordsPeakLiveForTest());
    o.put("nativeLiveBytes",NativeImageBacking.backingBytesLiveForTest());o.put("nativePeakBytes",NativeImageBacking.backingBytesPeakLiveForTest());
    o.put("nativeDerived",category(1));o.put("nativeDecoded",category(2));return o;
  }
  public JSONObject finish(Image[] images) throws JSONException {
    JSONObject o=frame();o.put("counters",causal.snapshot());
    o.put("detaches",AdmissionMemoryForTest.detaches);o.put("replacements",AdmissionMemoryForTest.replacements);
    o.put("invalidations",AdmissionMemoryForTest.invalidations);o.put("discardedPending",AdmissionMemoryForTest.pendingDiscarded);
    o.put("uniqueExactKeys",AdmissionMemoryForTest.keyCount);
    int admittedKeys=0;for(int k=0;k<AdmissionMemoryForTest.keyCount;k++)if(AdmissionMemoryForTest.keyAdmitted[k])admittedKeys++;
    o.put("uniqueAdmittedKeys",admittedKeys);
    JSONArray perImage=new JSONArray();int pending=0;long referencedDecodedBytes=0;
    for(int i=0;i<images.length;i++) {
      ImagePipeline p=images[i].pipelineForSmoke();boolean candidate=p.pendingForAdmissionProbe();if(candidate)pending++;
      ImageBacking decoded=p.root() instanceof EncodedImageSource?((EncodedImageSource)p.root()).decodedBackingForPreparationCleanup():null;
      if(decoded instanceof NativeImageBacking)referencedDecodedBytes+=((NativeImageBacking)decoded).backingBytesForTest();
      JSONObject row=new JSONObject();row.put("index",i);row.put("paints",AdmissionMemoryForTest.paints[i]);row.put("materializations",AdmissionMemoryForTest.mats[i]);
      row.put("admissions",AdmissionMemoryForTest.admissions[i]);row.put("hits",AdmissionMemoryForTest.hits[i]);row.put("pending",candidate);
      row.put("retained",p.retainedForAdmissionProbe()!=null);row.put("retainedBytes",p.retainedForAdmissionProbe()==null?0:AdmissionMemoryForTest.size(p.retainedForAdmissionProbe()));row.put("width",AdmissionMemoryForTest.widths[i]);row.put("height",AdmissionMemoryForTest.heights[i]);
      row.put("format",AdmissionMemoryForTest.formats[i]);row.put("rowBytes",AdmissionMemoryForTest.heights[i]==0?0:AdmissionMemoryForTest.bytes[i]/AdmissionMemoryForTest.heights[i]);row.put("bytes",AdmissionMemoryForTest.bytes[i]);perImage.put(row);
    }
    o.put("perImage",perImage);o.put("pendingAtEnd",pending);o.put("referencedDecodedBytes",referencedDecodedBytes);
    JSONObject wp=new JSONObject();String[] names={"attempts","hits","fallbacks","copiedBytes","clippedHits","opacityScans","opacityScanPixels","attemptNs","writeNs","fallbackNs","fallbackDraws"};
    for(int i=0;i<names.length;i++)wp.put(names[i],metric(102,i));o.put("writePixels",wp);
    if(metric(103,0)!=0)throw new IllegalStateException("summary mode accumulated draw records");
    // The natural ending snapshot above remains authoritative. GC diagnostic is separate.
    totalcross.sys.Vm.gc();totalcross.sys.Vm.gc();
    o.put("postGcNativeDerived",category(1));o.put("postGcNativeDecoded",category(2));
    o.put("postGcNativeLiveBytes",NativeImageBacking.backingBytesLiveForTest());
    AdmissionMemoryForTest.enabled=false;Image.immediateMaterializedAdmissionForTest=0;
    metric(108,0);metric(100,0);metric(200,0);causal.finish();return o;
  }
}
