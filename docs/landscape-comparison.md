# Landscape: where this tool sits

Research question asked: *do AI/"vibe-coded" 3D CT tools exist, and how does
this project compare to what is already out there?* Findings below, then the
comparison, then what it means for what we build next.

> Sourcing note: several publisher and vendor pages (JACR, arXiv, Sectra,
> Kitware, 3DICOM, Slicer discourse) returned HTTP 403 through this
> environment's proxy, so a few entries rest on search-result summaries rather
> than fetched full text. Those are flagged. Anything unverified is marked as
> such rather than asserted.

## 1. Are there vibe-coded 3D CT tools?

**Essentially none of note — and none that do surgical planning.**

What the literature has:

- **Reymus et al., *J Dent* 2026** (PMID 42361884) — the closest case: a
  clinician with no formal programming training shipped three MIT-licensed
  apps, including a **3D Slicer extension** for 3D morphology comparison.
  *Caveat: the GitHub URLs could not be located; the authors themselves say
  reproducibility "remains to be established".*
- **Bera et al., "Vibe Coding in Radiology", *JACR* 2026** (PMID 42000013) —
  five locally vibe-coded radiology tools. Paywalled; could not verify whether
  any are volumetric.
- **Hamurcu, *Surg Innov* 2026** (PMID 42389900) — states outright that
  "existing literature on vibe coding in medicine is sparse and limited to
  non-surgical specialties". Its one concrete tool is a scoring calculator.

What GitHub has: a long tail of small repos with a `CLAUDE.md` — mostly **2D**
DICOM viewers ([elgabrielc/dicom-viewer](https://github.com/elgabrielc/dicom-viewer)
lists 3D as *planned*), or **rendering libraries rather than applications**
([ThalesMMS/MTK](https://github.com/ThalesMMS/MTK), Swift/Metal volume
rendering, 4★). A few genuine 3D ones exist
([jinkoo2/vtk_image_labeler_3d](https://github.com/jinkoo2/vtk_image_labeler_3d),
[Dezmon/Volume-visualizer](https://github.com/Dezmon/Volume-visualizer)) but
they are annotation/visualisation, not planning.

Also worth knowing as an architectural reference (no AI attribution claimed):
[l5769389/DicomVisionClient](https://github.com/l5769389/DicomVisionClient),
213★, created 2026 — MPR, 4D, server-side volume rendering, QA tools.

**Conclusion: zero AI-built tools do orthopaedic surgical planning. The space
is open.**

## 2. Serious pre-op planning tools

| Tool | Open/Commercial | Plate/screw simulation? |
|---|---|---|
| **Sectra 3D Trauma** | Commercial | **Yes** — virtual fragment reduction + 3D implant templates from DePuy Synthes and Smith+Nephew. The closest thing to our goal |
| **mediCAD 3D** | Commercial | **Yes** — 3D osteotomy workflows (open/closed wedge, rotational) built with the AO Trauma DCP Task Force; 100k+ implant templates |
| **Materialise Mimics / ProPlan** | Commercial | **Yes**, but service-gated — planning runs *with a Materialise engineer*, not self-serve |
| **Brainlab TraumaCad** | Commercial | Mostly **2D** radiograph overlay templating |
| **Stryker Blueprint** | Commercial | Yes, but shoulder arthroplasty only |
| **PeekMed** | Commercial (FDA cleared) | Yes, for its indicated procedures |
| **3DICOM MD** | Commercial (cheap) | **Yes, manually** — imports implant STL/OBJ and lets you position it; ships a free CAD library including plates and screws |
| **3D Slicer** core | **Open (BSD)** | No implant module |
| **[OsteotomyPlanner](https://github.com/KitwareMedical/OsteotomyPlanner)** | Open, Slicer ext | **No** — cuts and repositions bone, then stops. 12★ |
| **[SlicerBoneReconstructionPlanner](https://github.com/SlicerIGT/SlicerBoneReconstructionPlanner)** | Open (BSD-3) | **No** native plate support; generates 3D-printable cutting guides. Mandible/fibula. 36★ |
| **[SlicerOrbitSurgerySim](https://github.com/chz31/SlicerOrbitSurgerySim)** | Open (MIT) | **Yes** — the only open-source plate-fit simulator found. Orbit only, 1★, bring your own plate geometry |
| **[PelvisFix](https://github.com/JiaxuanLLiu/PelvisFix)** | Open, Slicer | **Screws yes, plates no.** Pelvis only, 5★/3 commits — a research artifact |
| **FEBio / BoneMesh** | Open | Solver + FE meshing, not a planner |

## 3. The gap — and it is exactly our thesis

A surgeon wanting *"simulate my planned osteotomy + plating and see the
result"* today chooses between a **€20–40k PACS-locked commercial licence** and
**stitching together four open-source tools**. Free tools specifically lack:

1. **Any implant geometry.** OsteotomyPlanner, BoneReconstructionPlanner and
   Slicer core ship **zero** plates or screws.
2. **Plate-on-bone conformity** — "does this pre-contoured plate sit flush, and
   where does it stand off?" Open-source answer exists for orbits only.
3. **Screw trajectory + collision/purchase checking** against the fracture
   line, joint surface, far cortex, and other screws.
4. **A coupled cut → reposition → fixate → verify workflow.** Every open tool
   stops partway.
5. **Post-fixation quantitative readout** — restored NSA / mechanical axis /
   articular step-off in mm, i.e. the numbers that go on the op plan. *"Slicer
   measures distances and angles but nothing computes an ortho-specific plan
   report."*
6. **Plate pre-bending output** for contouring against a printed model.
7. **A surgeon-usable UI.** Slicer is a research platform; the clinical
   workflow demands deep Slicer literacy.

## 4. How this project compares today

| Capability | This tool | Open-source alternatives |
|---|---|---|
| DICOM → 3D bone | done | Slicer, InVesalius, 3DICOM |
| HU threshold / denoise / crop | done | Slicer Segment Editor |
| Isolate a bone by clicking | **done** (region pick + scissors) | Slicer Islands + Scissors (more steps, steeper UI) |
| Cross-section with capped face | done | Slicer (via reslice, less direct) |
| Fracture-line highlighting | done (curvature + feature edges) | not offered as such |
| Contralateral mirror + ICP + deviation map | done | SlicerMorph / manual |
| **Ortho measurement with targets and stage comparison** | **done** — gap #5 above | **nothing open does this** |
| Plan versioning + JSON save/load | done | BoneStory's provenance tree (0★, research) |
| **Osteotomy / fragment transform** | **not yet** | OsteotomyPlanner does this well |
| **Plate/screw placement** | **not yet** | essentially nothing open |
| FE stress analysis | not yet | FEBio + BoneMesh |

Honest reading: on **reconstruction, clean-up, and measurement** this is
already a tighter, more surgeon-shaped workflow than the free alternatives, and
the measurement-with-targets layer addresses a gap nothing open source fills.
On **simulation itself — moving fragments and applying hardware — we have not
started**, and that is the whole point of the tool.

## 5. What to reuse rather than rebuild

- **Osteotomy machinery**: [OsteotomyPlanner](https://github.com/KitwareMedical/OsteotomyPlanner)
  (Python, Kitware-quality, permissive) — cut/reposition/history is exactly the
  osteotomy half.
- **Plate fit metrics**: [SlicerOrbitSurgerySim](https://github.com/chz31/SlicerOrbitSurgerySim)
  (MIT) — its plate registration and plate-to-bone distance mapping generalise
  directly to long-bone plates.
- **Screw planning**: [PelvisFix](https://github.com/JiaxuanLLiu/PelvisFix) —
  reference for trajectory planning in Python.
- **Plan versioning idea**: [BoneStory_2](https://github.com/Bridxo/BoneStory_2)
  (Apache-2.0) provenance tree for comparing plan A/B/C.
- **Implant geometry — the critical decision.** Vendor CAD (DePuy, Stryker) is
  *not* publicly available; it reaches Sectra/mediCAD by commercial
  partnership. Model libraries (GrabCAD, Printables) carry per-model licences
  that generally forbid redistribution. **The defensible path is to *generate*
  generic AO-style geometry parametrically** — LCP/DCP hole patterns, 3.5/4.5 mm
  cortical and 4.0 mm cancellous screws — with
  [CadQuery](https://github.com/CadQuery/cadquery) or
  [build123d](https://github.com/gumyr/build123d). This sidesteps IP entirely
  and makes plate length, hole count and curvature *tunable parameters*, which
  is what "which plate fits this patient?" actually requires.
- **Auto bone segmentation** later: TotalSegmentator / MONAI Auto3DSeg.

## 6. Consequences for the roadmap

1. **Build fragment transforms next** (select a fragment → translate/rotate with
   a handle → landmarks move with it → measurements update). This is the
   smallest step that turns the measurement layer into an actual simulator, and
   it is what `docs/planning-loop.md` names as the blocking gap.
2. **Then parametric implants** (CadQuery-generated plate + screw), followed by
   plate-to-bone standoff mapping and screw-vs-articular-surface checking —
   reusing the two reference implementations above.
3. **Keep the measurement report as the differentiator.** It is the item the
   commercial tools sell and no open tool provides.
4. **Do not chase a Slicer rewrite.** Slicer is the richer substrate, but the
   identified gap is a *surgeon-usable focused workflow*, which is precisely
   what a standalone app does better.
