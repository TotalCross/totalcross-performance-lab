# Copyright (C) 2026 Amalgam Solucoes em TI Ltda
#
# SPDX-License-Identifier: LGPL-2.1-only

import copy
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from runners import run
from tools import copyrect_causal as causal
from tools.packaging.build_macos import selected_java_sources, PackageError
from tests.test_immediate_admission_probe import fixture as immediate_fixture

ROOT = Path(__file__).parents[1]
REASONS = ('invalidTargetOrSource', 'alphaMask', 'sourceRect', 'matrix',
           'fractionalDestination', 'sizeMismatch', 'destinationBounds', 'opacity',
           'unsupportedFormat', 'sourcePixels', 'writeFailure')


def writepixels():
    draws = []
    for i in range(18):
        x, y, height = 1 + 180*(i % 3), 42 + 181*(i // 3), 6 if i >= 15 else 358
        source, destination = [0, 0, 358, height], [x*2, y*2, x*2+358, y*2+height]
        draws.append(dict(sourceHandle=i+1, sourceFormat=0, sourceWidth=358, sourceHeight=358,
                          opacityBefore=1, opacityAfter=1, hit=True, rejection='none',
                          copiedBytes=358*height*4, clipped=False, sourcePhysical=source,
                          destinationLogical=[x, y, x+179, y+height/2], destinationDevice=destination,
                          clippedSourcePhysical=source, clippedDestinationDevice=destination,
                          canvasScaleTranslation=[2, 2, 0, 0], attemptNs=0, writeNs=0, fallbackNs=0))
    return dict(enabled=True, attempts=18, hits=18, fallbacks=0, copiedBytes=sum(d['copiedBytes'] for d in draws),
                clippedHits=0, opacityScans=0, opacityScanPixels=0, attemptNs=0, writeNs=0,
                fallbackNs=0, fallbackDraws=0, rejections=dict.fromkeys(REASONS, 0), draws=draws)


def fixture():
    r, entries = immediate_fixture()
    r['measurements'].update(scrollDriver='writepixels-warm-path-probe', writePixelsPolicy='historical-rgba-bit2')
    for s in [r['measurements']['stabilization'], *r['measurements']['samples']]:
        s['counters']['writePixels'] = writepixels()
    return r, entries


class WritePixelsWarmProbeTests(unittest.TestCase):
    def test_complete_protocol_and_partial_bottom_rectangles(self):
        r, entries = fixture()
        causal.validate_result(r, entries)
        self.assertEqual(7715616, r['measurements']['samples'][0]['counters']['writePixels']['copiedBytes'])

    def test_valid_rejection_is_preserved_without_forcing_hits(self):
        r, entries = fixture()
        wp = r['measurements']['samples'][0]['counters']['writePixels']
        d = wp['draws'][0]
        wp.update(hits=17, fallbacks=1, fallbackDraws=1, copiedBytes=wp['copiedBytes']-d['copiedBytes'])
        wp['rejections']['opacity'] = 1
        d.update(hit=False, rejection='opacity', copiedBytes=0, opacityAfter=2)
        causal.validate_result(r, entries)

    def test_reject_incomplete_inconsistent_or_unproven_hits(self):
        for mutate in (lambda w: w['draws'].pop(), lambda w: w.update(copiedBytes=1),
                       lambda w: w['draws'][0].update(opacityAfter=0),
                       lambda w: w['draws'][0].update(sourceFormat=1),
                       lambda w: w['draws'][0].update(clippedDestinationDevice=[0,0,1,1]),
                       lambda w: w['draws'][0].update(clippedSourcePhysical=[0,0,1.5,1]),
                       lambda w: w.update(enabled=False), lambda w: w.update(writeNs=1)):
            r, entries = fixture()
            mutate(r['measurements']['samples'][0]['counters']['writePixels'])
            with self.assertRaises(run.RunnerError): causal.validate_result(r, entries)

    def test_explicit_driver_policy_required(self):
        r, entries = fixture()
        r['measurements']['writePixelsPolicy'] = 'other'
        with self.assertRaises(run.RunnerError): causal.validate_result(r, entries)

    def test_only_exact_full_and_parent_runtime_patches_admitted(self):
        manifest = dict(profileInventory=['default'], profiles={'default': {
            'entryClass': 'totalcross.bench.imagerendering.profiles.WritePixelsWarmDefault'}},
            runtimeArtifactSourceCommit=causal.WRITEPIXELS_RUNTIME, totalcrossSourceCommit=causal.WRITEPIXELS_RUNTIME,
            buildConfiguration=dict(runtimeArtifactMode='local-release-build'))
        e = ROOT/'experiments/p12-writepixels-warm'
        good = [SimpleNamespace(returncode=0, stdout=(e/name).read_text()) for name in ('runtime.patch','writepixels.patch')]
        with patch.object(causal.subprocess, 'run', side_effect=good):
            self.assertTrue(causal.is_experiment_package(manifest, Path('/source'), 'writepixels-warm-path-probe'))
        with patch.object(causal.subprocess, 'run', side_effect=[good[0], SimpleNamespace(returncode=0,stdout='wrong')]):
            self.assertFalse(causal.is_experiment_package(manifest, Path('/source'), 'writepixels-warm-path-probe'))
        self.assertFalse(causal.is_experiment_package(manifest, Path('/source'), 'immediate-admission-probe'))

    def test_normal_and_prior_packages_exclude_new_hook(self):
        source = ROOT/'benchmarks/image-rendering/src/totalcross/bench/imagerendering'
        for args in ((), (True,), (False,True)):
            self.assertFalse(any(p.name=='ImageWritePixelsWarmHooks.java'
                                 for p in selected_java_sources(source, ('default',), *args)))
        files = selected_java_sources(source, ('default',), False, False, True)
        self.assertTrue(all(any(p.name==name for p in files) for name in
                            ('ImageCausalProbeHooks.java','ImageImmediateAdmissionHooks.java',
                             'ImageWritePixelsWarmHooks.java','WritePixelsWarmDefault.java')))
        with self.assertRaises(PackageError): selected_java_sources(source, ('compact',), False, False, True)
        with self.assertRaises(PackageError): selected_java_sources(source, ('default',), False, True, True)

    def test_single_process_constraints_and_inline_preflight(self):
        args = dict(scroll_driver='writepixels-warm-path-probe', family='scroll', profiles='default',
                    rounds=1,warmups=0,diagnostics=False,width=540,height=960,require_default_scroll_preflight=True)
        run.validate_scroll_driver_arguments(SimpleNamespace(**args))
        for bad in (dict(rounds=2),dict(warmups=1),dict(profiles='compact'),dict(diagnostics=True)):
            with self.assertRaises(run.RunnerError): run.validate_scroll_driver_arguments(SimpleNamespace(**{**args,**bad}))
        runner=(ROOT/'runners/run.py').read_text()
        start=runner.rindex('if getattr(arguments, "scroll_driver", "fixed-step") not in (')
        self.assertIn('"writepixels-warm-path-probe"',runner[start:runner.index('launch_preflight(',start)])

    def test_delta_preserves_sdk_routing_admission_and_representation(self):
        delta=(ROOT/'experiments/p12-writepixels-warm/writepixels.patch').read_text()
        paths=[line.split()[2] for line in delta.splitlines() if line.startswith('diff --git')]
        self.assertEqual(['a/TotalCrossVM/src/nm/ui/skia/skia_image_backing.cpp',
                          'a/TotalCrossVM/src/nm/ui/skia/skia_surface_test.cpp',
                          'a/TotalCrossVM/src/nm/ui/skia/skia_writepixels_probe.h'],paths)
        self.assertIn('static bool warmWritePixelsEnabledForTest;',delta)
        self.assertIn('warmWritePixelsEnabledForTest && backingAccountingForTest',delta)
        self.assertIn('source->format != BackingFormat::RGBA8888',delta)
        self.assertIn('source->generation',delta)
        self.assertNotIn('TotalCrossSDK/',delta)
        self.assertNotIn('skia_image_geometry', '\n'.join(paths))


if __name__ == '__main__':
    unittest.main()
