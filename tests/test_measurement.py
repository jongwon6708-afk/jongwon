"""Tests for the radiographic measurement / planning-loop framework."""

import math
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from bonesim.measurement import (  # noqa: E402
    Measurement, PlanningSession, angle_at_vertex, angle_between_lines,
    distance, femur_trauma_preset,
)


def test_distance_and_angles():
    assert math.isclose(distance((0, 0, 0), (3, 4, 0)), 5.0)
    # Right angle at the vertex.
    assert math.isclose(angle_at_vertex((1, 0, 0), (0, 0, 0), (0, 1, 0)), 90.0)
    # Parallel lines -> 0 degrees.
    assert math.isclose(
        angle_between_lines((0, 0, 0), (1, 0, 0), (0, 5, 0), (2, 5, 0)), 0.0,
        abs_tol=1e-9)
    # 45 degrees.
    assert math.isclose(
        angle_between_lines((0, 0, 0), (1, 0, 0), (0, 0, 0), (1, 1, 0)), 45.0)


def test_measurement_evaluates_from_landmarks():
    session = PlanningSession(patient_ref="TEST")
    session.add_measurement(Measurement(
        name="gap", kind="distance", points=["a", "b"],
        target=0.0, tolerance=2.0))
    pre = session.add_stage("pre-op")
    pre.add_landmark("a", (0, 0, 0))
    pre.add_landmark("b", (10, 0, 0))

    results = session.evaluate_stage("pre-op")
    assert math.isclose(results["gap"], 10.0)
    assert session.measurements[0].within_target(10.0) is False
    assert session.measurements[0].within_target(1.0) is True


def test_planning_loop_compare_stages():
    """Simulating a reduction should close the gap and be flagged on target."""
    session = PlanningSession(patient_ref="TEST")
    session.add_measurement(Measurement(
        name="Fracture gap", kind="distance", points=["prox", "dist"],
        target=0.0, tolerance=2.0))

    pre = session.add_stage("pre-op")
    pre.add_landmark("prox", (0, 0, 0))
    pre.add_landmark("dist", (0, 0, 12))     # 12 mm displaced

    plan = session.add_stage("plan-v1", note="simulated reduction")
    plan.add_landmark("prox", (0, 0, 0))
    plan.add_landmark("dist", (0, 0, 1.5))   # reduced to 1.5 mm

    report = session.compare("pre-op", "plan-v1")
    gap = report["Fracture gap"]
    assert math.isclose(gap["before"], 12.0)
    assert math.isclose(gap["after"], 1.5)
    assert gap["delta"] < 0                   # gap decreased
    assert gap["within_target"] is True


def test_missing_landmark_is_skipped_not_fatal():
    session = PlanningSession()
    session.add_measurement(Measurement(
        name="gap", kind="distance", points=["a", "b"]))
    stage = session.add_stage("pre-op")
    stage.add_landmark("a", (0, 0, 0))        # 'b' not placed yet
    assert session.evaluate_stage("pre-op") == {}


def test_roundtrip_save_load_preserves_values():
    session = PlanningSession(patient_ref="CASE-1")
    for m in femur_trauma_preset():
        session.add_measurement(m)
    stage = session.add_stage("pre-op")
    stage.add_landmark("femoral_head_center", (0, 0, 100))
    stage.add_landmark("neck_shaft_junction", (25, 0, 60))
    stage.add_landmark("shaft_distal", (25, 0, 0))
    before = session.evaluate_stage("pre-op")

    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "plan.json")
        session.save(path)
        reloaded = PlanningSession.load(path)

    after = reloaded.evaluate_stage("pre-op")
    assert reloaded.patient_ref == "CASE-1"
    assert set(before) == set(after)
    for name in before:
        assert math.isclose(before[name], after[name], rel_tol=1e-12)


def test_neck_shaft_angle_matches_clinical_convention():
    """The NSA must be the medial (obtuse) angle, ~125-135 deg when normal.

    Geometry: head centre up-and-medial from the neck/shaft junction, shaft
    running straight distally. Measuring the angle between the two axis lines
    would give the acute supplement (~39 deg) -- which is what this guards.
    """
    session = PlanningSession()
    for m in femur_trauma_preset():
        session.add_measurement(m)
    stage = session.add_stage("pre-op")
    stage.add_landmark("femoral_head_center", (0.0, 0.0, 50.0))
    stage.add_landmark("neck_shaft_junction", (40.0, 0.0, 0.0))
    stage.add_landmark("shaft_distal", (40.0, 0.0, -100.0))

    nsa = session.evaluate_stage("pre-op")["Neck-shaft angle"]
    assert math.isclose(nsa, 141.34, abs_tol=0.1), nsa
    assert 120.0 < nsa < 160.0  # physiological / coxa valga range


def test_varus_collapse_is_detected_as_off_target():
    """A varus (reduced) neck-shaft angle must fall outside the target band."""
    session = PlanningSession()
    for m in femur_trauma_preset():
        session.add_measurement(m)
    nsa_measure = next(m for m in session.measurements
                       if m.name == "Neck-shaft angle")

    stage = session.add_stage("post-op")
    # Head dropped into varus: only slightly above the junction.
    stage.add_landmark("femoral_head_center", (0.0, 0.0, 12.0))
    stage.add_landmark("neck_shaft_junction", (40.0, 0.0, 0.0))
    stage.add_landmark("shaft_distal", (40.0, 0.0, -100.0))

    nsa = session.evaluate_stage("post-op")["Neck-shaft angle"]
    assert nsa < 120.0, nsa                       # varus
    assert nsa_measure.within_target(nsa) is False


if __name__ == "__main__":
    test_distance_and_angles()
    test_measurement_evaluates_from_landmarks()
    test_planning_loop_compare_stages()
    test_missing_landmark_is_skipped_not_fatal()
    test_roundtrip_save_load_preserves_values()
    test_neck_shaft_angle_matches_clinical_convention()
    test_varus_collapse_is_detected_as_off_target()
    print("All measurement tests passed.")
