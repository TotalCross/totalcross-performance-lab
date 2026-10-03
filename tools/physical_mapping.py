# Copyright (C) 2026 Amalgam Solucoes em TI Ltda
#
# SPDX-License-Identifier: LGPL-2.1-only

"""Source-faithful evaluation of captured current-runtime physical mapping gates."""

import math
import struct

GATES = (
    "sourceBackingStable", "mutationGenerationsEqual", "compileGeometry", "noFill",
    "smoothEligible", "positiveAxisTransform", "integerTranslation", "positiveAxisCanvas",
    "aEqualsCanvasScaleX", "dEqualsCanvasScaleY", "sourceBoundsValid",
    "integerSourceCoordinates", "integerDeviceDestination", "equalDeviceSourceWidth",
    "equalDeviceSourceHeight",
)


def f32(value):
    return struct.unpack("f", struct.pack("f", value))[0]


def integer(value):
    return math.isfinite(value) and math.floor(value) == value


def compile_geometry(p):
    # Only supported actual-chain semantics; never approximate an unknown operation.
    if p["rootFrameCount"] != 1 or any(op not in (0, 1) for op in p["operations"]):
        raise ValueError("actual chain requires additional exact native compileGeometry semantics")
    valid = (all(p[k] > 0 for k in ("rootWidth", "rootHeight", "rootLogicalWidth", "rootLogicalHeight",
                                  "outputWidth", "outputHeight"))
             and all(math.isfinite(p[k]) and p[k] > 0 for k in
                     ("rootContentScale", "rootHwScaleW", "rootHwScaleH"))
             and p["operationCount"] > 0)
    if not valid:
        return None
    a, d = p["rootContentScale"] / p["rootHwScaleW"], p["rootContentScale"] / p["rootHwScaleH"]
    width, height = float(p["rootLogicalWidth"]), float(p["rootLogicalHeight"])
    b = c = tx = ty = 0.0
    smooth = False
    for index, op in enumerate(p["operations"]):
        out_w, out_h = p["dimensions"][2 * index:2 * index + 2]
        if out_w <= 0 or out_h <= 0:
            return None
        x, y = width / out_w, height / out_h
        old_a, old_b, old_c, old_d, old_tx, old_ty = a, b, c, d, tx, ty
        # Same geometryCompose sequence, including zero terms and tx/ty arithmetic.
        a, b = old_a * x + old_b * 0.0, old_a * 0.0 + old_b * y
        c, d = old_c * x + old_d * 0.0, old_c * 0.0 + old_d * y
        tx, ty = old_a * 0.0 + old_b * 0.0 + old_tx, old_c * 0.0 + old_d * 0.0 + old_ty
        width, height = float(out_w), float(out_h)
        smooth |= op == 1
    if abs(width - p["outputWidth"]) >= .001 or abs(height - p["outputHeight"]) >= .001:
        return None
    return dict(a=a, b=b, c=c, d=d, tx=tx, ty=ty, width=width, height=height, smooth=smooth, hasFill=False)


def copy_rect_geometry(p):
    """Normal ImageControl.copyRect, followed by skiaDrawGeometryPlan clipping."""
    sx = sy = 0
    width, height = p["outputWidth"], p["outputHeight"]
    dx, dy = p["drawX"] + p["graphicsTranslationX"], p["drawY"] + p["graphicsTranslationY"]
    left, top = p["clipX"] + p["graphicsTranslationX"], p["clipY"] + p["graphicsTranslationY"]
    right, bottom = left + p["clipWidth"], top + p["clipHeight"]
    if dx < left:
        delta = left - dx
        dx, sx, width = left, sx + delta, width - delta
    if dy < top:
        delta = top - dy
        dy, sy, height = top, sy + delta, height - delta
    width, height = min(width, right - dx), min(height, bottom - dy)
    return {"source": [sx, sy, sx + width, sy + height],
            "destination": [dx, dy, dx + width, dy + height],
            "visibleWidth": width, "visibleHeight": height}


def evaluate(p, allow_smooth=True):
    t = compile_geometry(p)
    rect = copy_rect_geometry(p)
    # skia_setSurfaceScale resets all other matrix terms before normal drawing.
    sx = sy = f32(p["graphicsContentScale"])
    values = [None] * 15
    values[0] = p["sourceBackingStable"]
    values[1] = p["sourceMutationGeneration"] == p["backingMutationGeneration"]
    values[2] = t is not None
    source = device = None
    if t is not None:
        values[3] = not t["hasFill"]
        values[4] = (not t["smooth"] or (allow_smooth and abs(p["outputContentScale"] - 1.0) >= .000001))
        values[5] = all(math.isfinite(t[k]) and t[k] > 0 for k in ("a", "d")) and t["b"] == t["c"] == 0
        values[6] = integer(t["tx"]) and integer(t["ty"])
        values[7] = math.isfinite(sx) and math.isfinite(sy) and sx > 0 and sy > 0
        values[8], values[9] = t["a"] == sx, t["d"] == sy
        l, top, r, bottom = rect["source"]
        source = [t["a"] * l + t["tx"], t["d"] * top + t["ty"],
                  t["a"] * r + t["tx"], t["d"] * bottom + t["ty"]]
        fl, ft, fr, fb = map(f32, source)
        root_w = p["rootWidthOfAllFrames"] if p["rootWidthOfAllFrames"] > 0 else p["rootWidth"]
        values[10] = (source[2] > source[0] and source[3] > source[1]
                      and source[0] >= 0 and source[1] >= 0
                      and source[2] <= p["backingWidth"] and source[3] <= p["backingHeight"]
                      and fl >= 0 and ft >= 0 and fr <= f32(root_w) and fb <= f32(p["rootHeight"])
                      and fr > fl and fb > ft)
        values[11] = all(integer(v) for v in source)
        dl, dt, dr, db = rect["destination"]
        device = [f32(sx * f32(dl)), f32(sy * f32(dt)), f32(sx * f32(dr)), f32(sy * f32(db))]
        values[12] = all(integer(v) for v in device)
        values[13] = f32(device[2] - device[0]) == source[2] - source[0]
        values[14] = f32(device[3] - device[1]) == source[3] - source[1]
    first = next((i + 1 for i, value in enumerate(values) if value is False), None)
    gates = [{"number": i + 1, "name": name, "pass": values[i],
              "reached": first is None or i + 1 <= first} for i, name in enumerate(GATES)]
    return {"allowSmooth": allow_smooth, "transform": t, "canvasScaleX": sx, "canvasScaleY": sy,
            "copyRect": rect, "mappedSource": source, "deviceDestination": device,
            "gates": gates, "firstFailingGate": first,
            "firstFailingGateName": GATES[first - 1] if first else None}


def validate_result(record, entries):
    from runners import run
    if (record.get("profile") != "default" or record.get("family") != "scroll"
            or record.get("renderer") != "RASTER" or record.get("diagnosticsEnabled") is not False
            or record.get("logicalDimensions") != {"width": 540, "height": 960}):
        raise run.RunnerError("physical-mapping-probe requires default RASTER with diagnostics disabled at 540x960")
    m = record["measurements"]
    run.validate_schema(m, run.read_json(run.SCHEMA_DIR / "physical-mapping-probe-v1.schema.json"), run.SCHEMA_DIR)
    if len(m["perControl"]) != 18:
        raise run.RunnerError("physical-mapping-probe requires eighteen controls")
    for i, control in enumerate(m["perControl"]):
        p = control["plan"]
        if (control["datasetIndex"] != i or control["rowIndex"] != i // 3
                or any(control[k] != entries[i][v] for k, v in
                       (("path", "path"), ("format", "format"), ("intrinsicWidth", "width"), ("intrinsicHeight", "height")))):
            raise run.RunnerError("physical mapping controls differ from manifest viewport order")
        if (len(p["operations"]) != p["operationCount"] or len(p["dimensions"]) != 2 * p["operationCount"]
                or len(p["parameters"]) != 4 * p["operationCount"]):
            raise run.RunnerError("physical mapping operation arrays are inconsistent")
        if not p["backingNative"] or not p["backingValid"] or p["backingWidth"] <= 0 or p["backingHeight"] <= 0:
            raise run.RunnerError("native source backing unavailable before compileGeometry")
        if p["hwScaleW"] != 1 or p["hwScaleH"] != 1:
            raise run.RunnerError("normal native draw requires unit presentation hardware scale")
        if p["destinationScale"] != p["graphicsContentScale"]:
            raise run.RunnerError("plan destination scale differs from normal Graphics destination")
        try:
            evaluated = evaluate(p)
            strict = evaluate(p, False)
        except ValueError as error:
            raise run.RunnerError(str(error)) from error
        if "evaluation" in control and control["evaluation"] != evaluated:
            raise run.RunnerError("physical mapping gate evaluation is inconsistent")
        if "identityDrawEvaluation" in control and control["identityDrawEvaluation"] != strict:
            raise run.RunnerError("strict identity evaluation is inconsistent")
        control["evaluation"], control["identityDrawEvaluation"] = evaluated, strict
