# Copyright (C) 2026 Amalgam Solucoes em TI Ltda
#
# SPDX-License-Identifier: LGPL-2.1-only
"""Validate fixed-route admission experiments without asserting a policy winner."""

def positions(maximum, step, repeated=False):
    down = list(range(0, maximum, step)) + [maximum]
    return down + [max(0, maximum - n * step) for n in range(1, (maximum + step - 1) // step + 1)] if repeated else down


def validate_result(record, entries, policy=None, workload=None):
    from runners import run
    def require(condition, message):
        if not condition:
            raise run.RunnerError("admission memory probe: " + message)
    m = record['measurements']
    run.validate_schema(m, run.read_json(run.SCHEMA_DIR / 'materialized-admission-memory-probe-v1.schema.json'), run.SCHEMA_DIR)
    require(record.get('profile') == 'default' and record.get('family') == 'scroll'
            and record.get('renderer') == 'RASTER' and record.get('diagnosticsEnabled') is False
            and record.get('logicalDimensions') == {'width': 540, 'height': 960}, 'runtime axes/profile')
    require(policy is None or policy == m['admissionPolicy'], 'policy differs from requested case')
    require(workload is None or workload == m['admissionWorkload'], 'workload differs from requested case')
    require(m['runtimeConfigurationBefore'] == m['runtimeConfigurationAfter'], 'runtime defaults changed')
    require(m['positions'] == positions(m['scrollMaximum'], 120 if m['admissionWorkload'] == 'repeated-scroll' else m['viewportHeight'], m['admissionWorkload'] == 'repeated-scroll'), 'route differs from deterministic definition')
    s = m['summary']; images = s['perImage']; frames = m['frames']
    require(len(entries) == len(images) == 663, 'dataset/control count')
    require([i['index'] for i in images] == list(range(663)), 'per-image order')
    require(all(i['paints'] > 0 and i['materializations'] > 0 for i in images), 'not every image encountered/materialized')
    require(sum(i['materializations'] for i in images) == s['materializations'], 'materialization conservation')
    require(sum(i['admissions'] for i in images) == s['admissions'], 'admission conservation')
    require(sum(i['retained'] for i in images) == s['cacheLiveCount'], 'retained count conservation')
    require(sum(i['retainedBytes'] for i in images) == s['cacheLiveBytes'], 'retained byte conservation')
    require(sum(i['pending'] for i in images) == s['pendingAtEnd'], 'pending conservation')
    require(s['admissions'] - s['detaches'] == s['cacheLiveCount'], 'slot installation/detach conservation')
    require(s['replacements'] <= s['detaches'] and s['uniqueAdmittedKeys'] <= s['uniqueExactKeys'], 'lifecycle key/count bounds')
    require(s['cachePeakCount'] <= 663 and s['cacheLiveCount'] <= s['cachePeakCount'], 'one slot capacity')
    require(s['cacheLiveBytes'] <= s['cachePeakBytes'] and s['nativeDerived']['liveBytes'] >= s['cacheLiveBytes'], 'derived/cache byte bounds')
    for snapshot in [s, *(f['memory'] for f in frames)]:
        derived, decoded = snapshot['nativeDerived'], snapshot['nativeDecoded']
        require(snapshot['nativeLiveBytes'] >= derived['liveBytes'] + decoded['liveBytes'], 'native storage category conservation')
        require(snapshot['nativeLiveCount'] >= derived['liveCount'] + decoded['liveCount'], 'native category count conservation')
        for category in (derived, decoded):
            require(category['liveCount'] <= category['peakCount'] and category['liveBytes'] <= category['peakBytes'], 'native category peak bounds')
    for i in images:
        require(i['width'] > 0 and i['height'] > 0 and i['bytes'] == i['rowBytes'] * i['height'], 'physical storage accounting')
        require(i['admissions'] <= i['materializations'], 'admissions exceed materializations')
    seen = []; previous = -1
    for f in frames:
        index = f['routeIndex']
        require(index in (previous, previous + 1), 'paint route order/skipped position')
        require(f['extraPaint'] == (index == previous), 'extra paint classification')
        require(f['position'] == m['positions'][index], 'paint outside planned route')
        if index != previous:
            seen.append(index)
        previous = index
    require(seen == list(range(len(m['positions']))), 'route incomplete')
    c = s['counters']
    require(c['cachedFinalRasterProbes'] == c['cachedFinalRasterHits'] + c['cachedFinalRasterMisses'], 'probe conservation')
    require(c['materializedVariantObservations'] >= s['materializations'] and c['materializedVariantAdmissions'] >= s['admissions'], 'registered/global accounting')
    require(s['writePixels']['attemptNs'] == s['writePixels']['writeNs'] == s['writePixels']['fallbackNs'] == 0, 'per-event native timers enabled')
    require(s['writePixels']['attempts'] == s['writePixels']['hits'] + s['writePixels']['fallbacks'], 'writePixels conservation')
