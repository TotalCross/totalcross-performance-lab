# Copyright (C) 2026 Amalgam Solucoes em TI Ltda
#
# SPDX-License-Identifier: LGPL-2.1-only
import copy
from pathlib import Path
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from tools import copyrect_causal as causal
from runners import run
from tools import materialized_admission_memory as memory
from tools.packaging.build_macos import selected_java_sources, PackageError

ROOT=Path(__file__).parents[1]

def fixture(policy='SECOND_OBSERVATION',workload='one-shot'):
    props=run.read_json(run.SCHEMA_DIR/'materialized-admission-memory-probe-v1.schema.json')['properties']
    def value(schema):
        if 'const' in schema:return schema['const']
        if 'enum' in schema:return schema['enum'][0]
        if schema.get('type')=='object':return {k:value(v) for k,v in schema.get('properties',{}).items()}
        if schema.get('type')=='array':return []
        if schema.get('type')=='boolean':return False
        if schema.get('type')=='string':return 'unchanged'
        return 0
    m={k:value(v) for k,v in props.items()}
    m.update(admissionPolicy=policy,admissionWorkload=workload,scrollMaximum=1810,workloadNs=100)
    m['positions']=memory.positions(1810,120 if workload=='repeated-scroll' else 910,workload=='repeated-scroll')
    s=m['summary']; admitted=policy=='IMMEDIATE' or workload=='repeated-scroll'; mats=2 if workload=='repeated-scroll' and policy=='SECOND_OBSERVATION' else 1
    itemSchema=props['summary']['properties']['perImage']['items']
    for i in range(663):
        row=value(itemSchema);row.update(index=i,paints=2 if workload=='repeated-scroll' else 1,materializations=mats,
            admissions=int(admitted),retained=admitted,retainedBytes=64 if admitted else 0,pending=not admitted,
            width=4,height=4,rowBytes=16,bytes=64)
        s['perImage'].append(row)
    s.update(materializations=663*mats,admissions=663 if admitted else 0,cacheLiveCount=663 if admitted else 0,
        cachePeakCount=663 if admitted else 0,cacheLiveBytes=663*64 if admitted else 0,cachePeakBytes=663*64 if admitted else 0,
        pendingAtEnd=0 if admitted else 663,uniqueExactKeys=663,uniqueAdmittedKeys=663 if admitted else 0)
    s['nativeDerived'].update(liveCount=663,peakCount=663,liveBytes=663*64,peakBytes=663*64)
    s.update(nativeLiveCount=663,nativePeakCount=663,nativeLiveBytes=663*64,nativePeakBytes=663*64)
    s['counters']={'cachedFinalRasterProbes':663,'cachedFinalRasterHits':0,'cachedFinalRasterMisses':663,
        'materializedVariantObservations':s['materializations'],'materializedVariantAdmissions':s['admissions']}
    frameSchema=props['frames']['items']
    for i,p in enumerate(m['positions']):
        frame=value(frameSchema);frame.update(routeIndex=i,position=p,paintTreeNs=1,elapsedNs=i+1);m['frames'].append(frame)
    return {'profile':'default','family':'scroll','renderer':'RASTER','diagnosticsEnabled':False,
            'logicalDimensions':{'width':540,'height':960},'measurements':m}

class AdmissionMemoryTest(unittest.TestCase):
    def validate(self,record):memory.validate_result(record,[{}]*663)
    def test_four_policy_workload_contracts(self):
        for policy in ('SECOND_OBSERVATION','IMMEDIATE'):
            for workload in ('one-shot','repeated-scroll'):self.validate(fixture(policy,workload))
    def test_routes_include_endpoints_and_do_not_artificially_revisit_one_shot(self):
        self.assertEqual(memory.positions(1810,910),[0,910,1810])
        self.assertEqual(memory.positions(250,120,True),[0,120,240,250,130,10,0])
    def test_unavoidable_extra_paint_is_preserved(self):
        r=fixture(); f=copy.deepcopy(r['measurements']['frames'][0]);f['extraPaint']=True
        r['measurements']['frames'].insert(1,f);self.validate(r)
        f['extraPaint']=False
        with self.assertRaises(run.RunnerError):self.validate(r)
    def test_missing_route_or_image_is_rejected(self):
        r=fixture();r['measurements']['frames'].pop()
        with self.assertRaises(run.RunnerError):self.validate(r)
        r=fixture();r['measurements']['summary']['perImage'][400]['paints']=0
        with self.assertRaises(run.RunnerError):self.validate(r)
    def test_cache_ownership_and_native_temporaries_are_distinct(self):
        r=fixture();self.validate(r)
        self.assertEqual(r['measurements']['summary']['cacheLiveBytes'],0)
        self.assertGreater(r['measurements']['summary']['nativeDerived']['liveBytes'],0)
        r=fixture('IMMEDIATE');r['measurements']['summary']['cacheLiveBytes']+=1
        with self.assertRaises(run.RunnerError):self.validate(r)
    def test_policy_route_and_timers_are_guarded(self):
        r=fixture()
        with self.assertRaises(run.RunnerError):memory.validate_result(r,[{}]*663,'IMMEDIATE','one-shot')
        r['measurements']['summary']['writePixels']['attemptNs']=1
        with self.assertRaises(run.RunnerError):self.validate(r)
    def test_package_selection_isolated_from_normal(self):
        src=ROOT/'benchmarks/image-rendering/src/totalcross/bench/imagerendering'
        normal=selected_java_sources(src,('default',));experimental=selected_java_sources(src,('default',),memory_experiment=True)
        self.assertFalse(any('p12-admission-memory' in str(p) for p in normal))
        self.assertTrue(any(p.name=='ImageAdmissionMemoryHooks.java' for p in experimental))
        with self.assertRaises(PackageError):selected_java_sources(src,('default','compact'),memory_experiment=True)
    def test_exact_runtime_full_patch_and_parent_delta_are_required(self):
        manifest=dict(profileInventory=['default'],profiles={'default':{'entryClass':'totalcross.bench.imagerendering.profiles.MaterializedAdmissionMemoryDefault'}},runtimeArtifactSourceCommit=causal.MEMORY_RUNTIME,totalcrossSourceCommit=causal.MEMORY_RUNTIME,buildConfiguration={'runtimeArtifactMode':'local-release-build'})
        exp=ROOT/'experiments/p12-admission-memory'
        good=[SimpleNamespace(returncode=0,stdout=(exp/name).read_text()) for name in ('runtime.patch','memory.patch')]
        with patch.object(causal.subprocess,'run',side_effect=good):self.assertTrue(causal.is_experiment_package(manifest,Path('/source'),'materialized-admission-memory-probe'))
        with patch.object(causal.subprocess,'run',side_effect=[good[0],SimpleNamespace(returncode=0,stdout='wrong')]):self.assertFalse(causal.is_experiment_package(manifest,Path('/source'),'materialized-admission-memory-probe'))
    def test_one_process_default_only_and_inline_preflight(self):
        args=dict(scroll_driver='materialized-admission-memory-probe',family='scroll',profiles='default',rounds=1,warmups=0,diagnostics=False,width=540,height=960,require_default_scroll_preflight=True)
        run.validate_scroll_driver_arguments(SimpleNamespace(**args))
        for change in ({'rounds':2},{'warmups':1},{'profiles':'compact'}):
            with self.assertRaises(run.RunnerError):run.validate_scroll_driver_arguments(SimpleNamespace(**{**args,**change}))
        runner=(ROOT/'runners/run.py').read_text();start=runner.rindex('if getattr(arguments, "scroll_driver", "fixed-step") not in (')
        self.assertIn('"materialized-admission-memory-probe"',runner[start:runner.index('launch_preflight(',start)])
    def test_no_synthetic_resolve_or_prepare_in_protocol(self):
        src=(ROOT/'benchmarks/image-rendering/src/totalcross/bench/imagerendering/ScrollWorkload.java').read_text()
        body=src[src.index('  private void advanceAdmissionMemory'):src.index('  private void beginPass')]
        self.assertNotIn('resolveForDrawing(',body);self.assertNotIn('prepareForDisplay(',body)
        self.assertNotIn('paintTreeOnly()',body);self.assertIn('Window.needsPaint=true',body)
