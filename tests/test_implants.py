"""Tests for parametric implants and fixation analysis."""

import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))

from bonesim import fixation, implants, simulation  # noqa: E402
from test_simulation import _bone  # noqa: E402


# ------------------------------------------------------------------ geometry
def test_screw_has_expected_length_and_diameter():
    spec = implants.ScrewSpec(length_mm=40.0, diameter_mm=3.5,
                              head_diameter_mm=6.0)
    screw = implants.make_screw(spec, spacing=0.4)
    assert screw.GetNumberOfCells() > 0
    b = screw.GetBounds()
    # Runs from the head (z~0) down to the tip (z~-40).
    assert math.isclose(b[5] - b[4], spec.length_mm + spec.head_height_mm,
                        abs_tol=1.5), b
    # Widest part is the head.
    assert math.isclose(b[1] - b[0], spec.head_diameter_mm, abs_tol=1.0), b


def test_plate_holes_reduce_volume():
    solid = implants.PlateSpec(hole_count=0)
    holed = implants.PlateSpec(hole_count=6)
    v_solid = fixation.mesh_volume(implants.make_plate(solid, spacing=0.5))
    v_holed = fixation.mesh_volume(implants.make_plate(holed, spacing=0.5))
    assert v_solid > 0
    assert v_holed < v_solid, (v_solid, v_holed)


def test_plate_hole_positions_are_evenly_spaced_and_centred():
    spec = implants.PlateSpec(length_mm=90.0, hole_count=6)
    positions = spec.hole_positions
    assert len(positions) == 6
    gaps = [b - a for a, b in zip(positions, positions[1:])]
    assert all(math.isclose(g, gaps[0], rel_tol=1e-9) for g in gaps)
    assert math.isclose(sum(positions), 0.0, abs_tol=1e-9)  # centred
    assert min(positions) > -spec.length_mm / 2
    assert max(positions) < spec.length_mm / 2


def test_place_along_aims_tip_at_target():
    screw = implants.make_screw(implants.ScrewSpec(length_mm=30.0),
                                spacing=0.5)
    entry, target = (0.0, 0.0, 0.0), (30.0, 0.0, 0.0)
    placed = implants.place_along(screw, entry, target)
    b = placed.GetBounds()
    # The screw should now run along +x from the entry toward the target.
    assert b[1] > 25.0, b
    assert abs(b[0]) < 3.0, b
    assert (b[3] - b[2]) < 8.0, b   # thin in y


# ------------------------------------------------------------------ fixation
def test_screw_purchase_high_inside_bone_low_outside():
    bone = _bone()
    b = bone.GetBounds()
    cx, cy = (b[0] + b[1]) / 2, (b[2] + b[3]) / 2
    screw = implants.make_screw(
        implants.ScrewSpec(length_mm=16.0, diameter_mm=3.5), spacing=0.4)

    # Driven down the middle of the bone: mostly in bone.
    inside = implants.place_along(
        screw, (cx, cy, b[5] - 1.0), (cx, cy, b[5] - 17.0))
    good = fixation.screw_purchase(inside, bone, spacing=0.5)
    assert good["purchase_fraction"] > 0.6, good

    # Parked well clear of the bone: no purchase.
    outside = implants.place_along(
        screw, (b[1] + 40.0, cy, b[5]), (b[1] + 40.0, cy, b[5] - 16.0))
    poor = fixation.screw_purchase(outside, bone, spacing=0.5)
    assert poor["purchase_fraction"] < 0.05, poor


def test_lag_screw_must_cross_the_fracture_plane():
    bone = _bone()
    b = bone.GetBounds()
    cx, cy = (b[0] + b[1]) / 2, (b[2] + b[3]) / 2
    zmid = (b[4] + b[5]) / 2
    plane = ((cx, cy, zmid), (0.0, 0.0, 1.0))

    # Crosses the fracture -> a true lag screw.
    long_screw = implants.make_screw(
        implants.ScrewSpec(length_mm=20.0), spacing=0.5)
    crossing = implants.place_along(
        long_screw, (cx, cy, zmid + 9.0), (cx, cy, zmid - 9.0))
    assert fixation.crosses_plane(crossing, *plane) is True

    # A screw too short to reach the fracture stays in one fragment and so
    # cannot lag, however well it is seated. place_along keeps the screw's own
    # length, so this is decided by the length chosen -- not by the target.
    short_screw = implants.make_screw(
        implants.ScrewSpec(length_mm=6.0), spacing=0.4)
    contained = implants.place_along(
        short_screw, (cx, cy, b[5] - 0.5), (cx, cy, zmid))
    assert fixation.crosses_plane(contained, *plane) is False

    # And the helper reports the length actually needed to span the fracture.
    needed = implants.length_for_trajectory(
        (cx, cy, b[5] - 0.5), (cx, cy, zmid - 5.0))
    assert needed > 6.0


def test_articular_breach_detected():
    bone = _bone()
    b = bone.GetBounds()
    cx, cy = (b[0] + b[1]) / 2, (b[2] + b[3]) / 2
    # Treat the top slice of the bone as the "articular surface".
    joint = simulation.osteotomy_cut(
        bone, (cx, cy, b[5] - 2.0), (0.0, 0.0, 1.0))[0]

    screw = implants.make_screw(
        implants.ScrewSpec(length_mm=14.0), spacing=0.5)
    # Aimed up through the joint surface.
    through = implants.place_along(
        screw, (cx, cy, b[5] - 12.0), (cx, cy, b[5] + 2.0))
    assert fixation.articular_breach(through, joint)["breached"] is True

    # Aimed away from the joint, deep in the shaft.
    away = implants.place_along(
        screw, (cx, cy, b[4] + 12.0), (cx, cy, b[4] + 1.0))
    assert fixation.articular_breach(away, joint)["breached"] is False


def test_screw_screw_conflict_flagged_when_parallel_and_close():
    screw = implants.make_screw(
        implants.ScrewSpec(length_mm=20.0, diameter_mm=3.5), spacing=0.5)
    a = implants.place_along(screw, (0.0, 0.0, 0.0), (0.0, 0.0, -20.0))
    near = implants.place_along(screw, (3.0, 0.0, 0.0), (3.0, 0.0, -20.0))
    far = implants.place_along(screw, (20.0, 0.0, 0.0), (20.0, 0.0, -20.0))

    assert fixation.screw_screw_conflict(a, near)["too_close"] is True
    assert fixation.screw_screw_conflict(a, far)["too_close"] is False


def test_plate_standoff_grows_when_lifted_off_bone():
    bone = _bone()
    b = bone.GetBounds()
    plate = implants.make_plate(
        implants.PlateSpec(length_mm=20.0, width_mm=10.0, hole_count=3),
        spacing=0.6)

    # Lay the plate just outside the lateral cortex.
    on_bone = implants.place_along(
        plate, ((b[0] + b[1]) / 2, b[2] - 1.0, (b[4] + b[5]) / 2),
        ((b[0] + b[1]) / 2, b[2] - 1.0, b[4]))
    lifted = simulation.transform_mesh(
        on_bone, simulation.build_transform(translation=(0.0, -8.0, 0.0)))

    near = fixation.plate_standoff(on_bone, bone)
    far = fixation.plate_standoff(lifted, bone)
    assert far["min_mm"] > near["min_mm"] + 5.0, (near, far)


def test_construct_report_covers_every_screw():
    bone = _bone()
    b = bone.GetBounds()
    cx, cy = (b[0] + b[1]) / 2, (b[2] + b[3]) / 2
    zmid = (b[4] + b[5]) / 2
    screw = implants.make_screw(implants.ScrewSpec(length_mm=18.0),
                                spacing=0.5)
    screws = [
        implants.place_along(screw, (cx, cy, zmid + 8.0), (cx, cy, zmid - 8.0)),
        implants.place_along(screw, (cx + 6.0, cy, zmid + 8.0),
                             (cx + 6.0, cy, zmid - 8.0)),
    ]
    report = fixation.construct_report(
        bone, screws, fracture_plane=((cx, cy, zmid), (0.0, 0.0, 1.0)))
    assert len(report["screws"]) == 2
    for entry in report["screws"]:
        assert "purchase_fraction" in entry
        assert entry["lags_fracture"] is True


if __name__ == "__main__":
    test_screw_has_expected_length_and_diameter()
    test_plate_holes_reduce_volume()
    test_plate_hole_positions_are_evenly_spaced_and_centred()
    test_place_along_aims_tip_at_target()
    test_screw_purchase_high_inside_bone_low_outside()
    test_lag_screw_must_cross_the_fracture_plane()
    test_articular_breach_detected()
    test_screw_screw_conflict_flagged_when_parallel_and_close()
    test_plate_standoff_grows_when_lifted_off_bone()
    test_construct_report_covers_every_screw()
    print("All implant/fixation tests passed.")
