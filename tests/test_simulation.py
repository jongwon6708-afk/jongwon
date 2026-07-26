"""Tests for osteotomy cutting and fragment repositioning."""

import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))

from bonesim.reconstruction import ReconstructionParams, reconstruct_bone  # noqa: E402
from bonesim.preprocessing import PreprocessParams  # noqa: E402
from bonesim import simulation  # noqa: E402
from bonesim.measurement import (  # noqa: E402
    Measurement, PlanningSession,
)
from test_editing import make_two_bones_phantom  # noqa: E402


def _bone():
    """A single isolated solid bone from the two-bone phantom."""
    from bonesim import editing
    volume = make_two_bones_phantom()
    mesh = reconstruct_bone(volume, ReconstructionParams(
        threshold_hu=500, smoothing_iterations=0, decimation=0.0,
        island_min_fraction=0.0,
        preprocess=PreprocessParams(median_denoise=False)))
    # Keep the compact left-most structure (a bone, not the table slab).
    best = None
    for rid in range(len(editing.region_sizes(mesh))):
        rb = editing.extract_regions(mesh, {rid}, invert=False).GetBounds()
        if (rb[1] - rb[0]) / max(rb[3] - rb[2], 1e-6) < 3.0:
            if best is None or rb[0] < best[0]:
                best = (rb[0], rid)
    return editing.extract_regions(mesh, {best[1]}, invert=False)


def test_osteotomy_splits_into_two_fragments():
    bone = _bone()
    b = bone.GetBounds()
    zmid = (b[4] + b[5]) / 2
    origin = ((b[0] + b[1]) / 2, (b[2] + b[3]) / 2, zmid)

    upper, lower = simulation.osteotomy_cut(bone, origin, (0, 0, 1))
    assert upper.GetNumberOfCells() > 0
    assert lower.GetNumberOfCells() > 0
    # The two halves sit on opposite sides of the cut plane.
    assert upper.GetBounds()[4] >= zmid - 1.0
    assert lower.GetBounds()[5] <= zmid + 1.0
    # Together they span the original bone.
    assert math.isclose(upper.GetBounds()[5], b[5], abs_tol=1.0)
    assert math.isclose(lower.GetBounds()[4], b[4], abs_tol=1.0)


def test_translation_moves_fragment_by_exact_amount():
    bone = _bone()
    before = bone.GetBounds()
    tf = simulation.build_transform(translation=(10.0, 0.0, 0.0))
    moved = simulation.transform_mesh(bone, tf)
    after = moved.GetBounds()
    assert math.isclose(after[0] - before[0], 10.0, abs_tol=1e-6)
    assert math.isclose(after[1] - before[1], 10.0, abs_tol=1e-6)


def test_rotation_about_centroid_keeps_centroid_fixed():
    bone = _bone()
    pivot = simulation.centroid(bone)
    tf = simulation.build_transform(rotation_xyz=(0.0, 0.0, 30.0), pivot=pivot)
    rotated = simulation.transform_mesh(bone, tf)
    new_pivot = simulation.centroid(rotated)
    for a, b in zip(pivot, new_pivot):
        assert math.isclose(a, b, abs_tol=1.0)


def test_landmarks_follow_their_fragment():
    tf = simulation.build_transform(translation=(0.0, 0.0, 5.0))
    landmarks = {"on_frag": (0.0, 0.0, 0.0), "elsewhere": (0.0, 0.0, 0.0)}
    moved = simulation.transform_landmarks(landmarks, {"on_frag"}, tf)
    assert math.isclose(moved["on_frag"][2], 5.0)
    assert math.isclose(moved["elsewhere"][2], 0.0)  # untouched


def test_reduction_closes_the_gap_and_measurement_agrees():
    """End-to-end: cut, displace, then reduce -- the gap must shrink."""
    bone = _bone()
    b = bone.GetBounds()
    zmid = (b[4] + b[5]) / 2
    origin = ((b[0] + b[1]) / 2, (b[2] + b[3]) / 2, zmid)
    upper, lower = simulation.osteotomy_cut(bone, origin, (0, 0, 1))

    # Displace the upper fragment by 12 mm -- the injured state.
    displaced_tf = simulation.build_transform(translation=(0.0, 0.0, 12.0))
    displaced = simulation.transform_mesh(upper, displaced_tf)
    gap_injured = simulation.fragment_gap(displaced, lower)
    assert gap_injured > 8.0, gap_injured

    # Simulate a reduction bringing it back to within 1.5 mm.
    reduce_tf = simulation.build_transform(translation=(0.0, 0.0, -10.5))
    reduced = simulation.transform_mesh(displaced, reduce_tf)
    gap_reduced = simulation.fragment_gap(reduced, lower)
    assert gap_reduced < gap_injured
    assert gap_reduced < 3.0, gap_reduced


def test_overlap_distinguishes_over_reduction_from_true_reduction():
    """A zero gap from interpenetration must NOT read as a good reduction."""
    bone = _bone()
    b = bone.GetBounds()
    zmid = (b[4] + b[5]) / 2
    origin = ((b[0] + b[1]) / 2, (b[2] + b[3]) / 2, zmid)
    upper, lower = simulation.osteotomy_cut(bone, origin, (0, 0, 1))

    # Anatomically reduced: fragments touching along the shared cut face.
    good = simulation.reduction_quality(upper, lower)
    assert good["gap_mm"] < 2.0
    assert good["overlap_mm3"] < 50.0, good       # contact, not penetration
    assert good["verdict"] == "reduced"

    # Driven 6 mm into each other: gap still ~0, but this is over-reduction.
    driven = simulation.transform_mesh(
        upper, simulation.build_transform(translation=(0.0, 0.0, -6.0)))
    bad = simulation.reduction_quality(driven, lower)
    assert bad["gap_mm"] < 2.0                    # gap alone looks fine...
    assert bad["overlap_mm3"] > 1000.0, bad       # ...but they interpenetrate
    assert bad["verdict"] == "over-reduced (fragments interpenetrate)"

    # Pulled apart: plainly gapped.
    apart = simulation.transform_mesh(
        upper, simulation.build_transform(translation=(0.0, 0.0, 10.0)))
    assert simulation.reduction_quality(apart, lower)["verdict"] == "gapped"


def test_simulated_plan_updates_measurements_via_landmarks():
    """Moving a fragment must change the measured angle on the next stage."""
    session = PlanningSession()
    session.add_measurement(Measurement(
        name="Angulation", kind="angle",
        points=["distal", "apex", "proximal"],
        target=180.0, tolerance=5.0))

    # Pre-op: 20 degrees of apex angulation.
    pre = session.add_stage("pre-op")
    pre.add_landmark("apex", (0.0, 0.0, 0.0))
    pre.add_landmark("proximal", (0.0, 0.0, 50.0))
    angle_rad = math.radians(20.0)
    pre.add_landmark("distal", (
        math.sin(angle_rad) * 50.0, 0.0, -math.cos(angle_rad) * 50.0))
    before = session.evaluate_stage("pre-op")["Angulation"]
    assert math.isclose(before, 160.0, abs_tol=0.5), before

    # Plan: rotate the distal fragment 20 degrees about the apex to straighten.
    tf = simulation.build_transform(
        rotation_xyz=(0.0, 20.0, 0.0), pivot=(0.0, 0.0, 0.0))
    plan = session.add_stage("plan-v1")
    moved = simulation.transform_landmarks(
        {n: lm.position for n, lm in pre.landmarks.items()}, {"distal"}, tf)
    for name, pos in moved.items():
        plan.add_landmark(name, pos)

    after = session.evaluate_stage("plan-v1")["Angulation"]
    assert math.isclose(after, 180.0, abs_tol=0.5), after
    report = session.compare("pre-op", "plan-v1")
    assert report["Angulation"]["within_target"] is True


if __name__ == "__main__":
    test_osteotomy_splits_into_two_fragments()
    test_translation_moves_fragment_by_exact_amount()
    test_rotation_about_centroid_keeps_centroid_fixed()
    test_landmarks_follow_their_fragment()
    test_reduction_closes_the_gap_and_measurement_agrees()
    test_overlap_distinguishes_over_reduction_from_true_reduction()
    test_simulated_plan_updates_measurements_via_landmarks()
    print("All simulation tests passed.")
