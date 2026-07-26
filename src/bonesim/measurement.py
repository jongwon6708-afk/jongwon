"""Radiographic measurement for iterative surgical planning.

The planning loop this supports:

    reconstruct -> place landmarks -> measure -> simulate the plan
      -> re-measure on the simulated result -> compare against the target
      -> adjust the plan -> repeat

For that to work, measurements have to be *reproducible* and *comparable
across versions*. So landmarks are stored in patient (world) coordinates, each
measurement is derived from named landmarks rather than from raw numbers, and
a whole session serialises to JSON -- letting you diff pre-op vs a simulated
plan vs post-op, and re-derive every value if a landmark is moved.

Angle conventions follow standard orthopaedic radiographic measurement: angles
are reported in degrees in [0, 180], distances in millimetres.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field

Vec3 = tuple[float, float, float]


# ------------------------------------------------------------------- maths
def _sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _norm(v: Vec3) -> float:
    return math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2)


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def distance(a: Vec3, b: Vec3) -> float:
    """Straight-line distance in millimetres."""
    return _norm(_sub(a, b))


def angle_between_lines(a1: Vec3, a2: Vec3, b1: Vec3, b2: Vec3) -> float:
    """Angle in degrees between line a1->a2 and line b1->b2.

    Returned in [0, 180]; direction of each line does not matter beyond that,
    which matches how radiographic angles are read off a film.
    """
    u, v = _sub(a2, a1), _sub(b2, b1)
    nu, nv = _norm(u), _norm(v)
    if nu < 1e-9 or nv < 1e-9:
        raise ValueError("Degenerate line: the two points coincide")
    cos = max(-1.0, min(1.0, _dot(u, v) / (nu * nv)))
    return math.degrees(math.acos(cos))


def angle_at_vertex(p1: Vec3, vertex: Vec3, p2: Vec3) -> float:
    """Angle in degrees subtended at *vertex* by p1 and p2."""
    return angle_between_lines(vertex, p1, vertex, p2)


# -------------------------------------------------------------- data model
@dataclass
class Landmark:
    """A named anatomical point in patient (world) coordinates, in mm."""

    name: str
    position: Vec3
    note: str = ""


@dataclass
class Measurement:
    """A measurement derived from landmark *names*, not from copied numbers.

    kind:
        "distance"  -> points = [a, b]
        "angle"     -> points = [p1, vertex, p2]
        "line_angle"-> points = [a1, a2, b1, b2]
    """

    name: str
    kind: str
    points: list[str]
    target: float | None = None      # planned/normal value, if any
    tolerance: float | None = None   # acceptable deviation from target

    def evaluate(self, landmarks: dict[str, Landmark]) -> float:
        try:
            pts = [landmarks[n].position for n in self.points]
        except KeyError as exc:
            raise KeyError(f"{self.name}: missing landmark {exc}") from exc

        if self.kind == "distance":
            if len(pts) != 2:
                raise ValueError(f"{self.name}: distance needs 2 points")
            return distance(*pts)
        if self.kind == "angle":
            if len(pts) != 3:
                raise ValueError(f"{self.name}: angle needs 3 points")
            return angle_at_vertex(pts[0], pts[1], pts[2])
        if self.kind == "line_angle":
            if len(pts) != 4:
                raise ValueError(f"{self.name}: line_angle needs 4 points")
            return angle_between_lines(*pts)
        raise ValueError(f"{self.name}: unknown measurement kind {self.kind!r}")

    def within_target(self, value: float) -> bool | None:
        """True/False if a target is set (tolerance defaults to 0), else None."""
        if self.target is None:
            return None
        tol = self.tolerance if self.tolerance is not None else 0.0
        return abs(value - self.target) <= tol


@dataclass
class PlanStage:
    """One version in the planning loop: pre-op, a simulated plan, post-op.

    Landmarks are stored per stage because simulating a reduction or osteotomy
    moves the bone -- and therefore the landmarks -- while the *definitions* of
    the measurements stay the same.
    """

    label: str
    landmarks: dict[str, Landmark] = field(default_factory=dict)
    note: str = ""

    def add_landmark(self, name: str, position: Vec3, note: str = "") -> None:
        self.landmarks[name] = Landmark(name=name, position=position, note=note)


@dataclass
class PlanningSession:
    """Measurement definitions plus every stage they are evaluated on."""

    patient_ref: str = ""
    measurements: list[Measurement] = field(default_factory=list)
    stages: list[PlanStage] = field(default_factory=list)

    # -- construction ----------------------------------------------------
    def add_measurement(self, measurement: Measurement) -> None:
        self.measurements.append(measurement)

    def add_stage(self, label: str, note: str = "") -> PlanStage:
        stage = PlanStage(label=label, note=note)
        self.stages.append(stage)
        return stage

    def stage(self, label: str) -> PlanStage:
        for s in self.stages:
            if s.label == label:
                return s
        raise KeyError(f"No stage named {label!r}")

    # -- evaluation ------------------------------------------------------
    def evaluate_stage(self, label: str) -> dict[str, float]:
        """Every measurement that can be computed for one stage."""
        stage = self.stage(label)
        results: dict[str, float] = {}
        for m in self.measurements:
            try:
                results[m.name] = m.evaluate(stage.landmarks)
            except KeyError:
                continue  # landmark not placed on this stage yet
        return results

    def compare(self, from_label: str, to_label: str) -> dict[str, dict]:
        """Change in every shared measurement between two stages.

        This is the core of the iteration loop: "what did my simulated plan
        actually change, and did it reach the target?"
        """
        before = self.evaluate_stage(from_label)
        after = self.evaluate_stage(to_label)
        targets = {m.name: m for m in self.measurements}

        report: dict[str, dict] = {}
        for name in sorted(set(before) & set(after)):
            m = targets[name]
            report[name] = {
                "before": before[name],
                "after": after[name],
                "delta": after[name] - before[name],
                "target": m.target,
                "within_target": m.within_target(after[name]),
            }
        return report

    # -- persistence -----------------------------------------------------
    def to_json(self, indent: int = 2) -> str:
        return json.dumps(asdict(self), indent=indent)

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(self.to_json())

    @classmethod
    def from_json(cls, text: str) -> "PlanningSession":
        raw = json.loads(text)
        session = cls(patient_ref=raw.get("patient_ref", ""))
        for m in raw.get("measurements", []):
            session.measurements.append(Measurement(**m))
        for s in raw.get("stages", []):
            stage = session.add_stage(s["label"], s.get("note", ""))
            for name, lm in s.get("landmarks", {}).items():
                stage.landmarks[name] = Landmark(
                    name=lm["name"],
                    position=tuple(lm["position"]),
                    note=lm.get("note", ""),
                )
        return session

    @classmethod
    def load(cls, path: str) -> "PlanningSession":
        with open(path, encoding="utf-8") as fh:
            return cls.from_json(fh.read())


# ------------------------------------------------------- standard presets
def femur_trauma_preset() -> list[Measurement]:
    """Common measurements for proximal-femur / shaft trauma planning.

    Landmark names the caller must place:
      femoral_head_center, neck_shaft_junction, shaft_distal,
      fragment_prox, fragment_dist

    The neck-shaft angle follows the clinical convention: it is the angle
    subtended at the neck/shaft junction between the ray to the femoral head
    centre and the ray down the shaft, i.e. the angle opening medially
    (normal ~125-135 degrees). Measuring it as the plain angle between the two
    axis *lines* would instead give its acute supplement, which is why this is
    a vertex angle rather than a line angle.
    """
    return [
        Measurement(
            name="Neck-shaft angle",
            kind="angle",
            points=["femoral_head_center", "neck_shaft_junction",
                    "shaft_distal"],
            target=128.0, tolerance=5.0,
        ),
        Measurement(
            name="Fracture gap",
            kind="distance",
            points=["fragment_prox", "fragment_dist"],
            target=0.0, tolerance=2.0,
        ),
        Measurement(
            name="Femoral offset",
            kind="distance",
            points=["femoral_head_center", "neck_shaft_junction"],
        ),
    ]
