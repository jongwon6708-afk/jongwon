"""3D Bone CT Simulator.

A static (post-operative) bone reconstruction and viewing tool.

Pipeline:
    DICOM (CT series) -> HU volume -> threshold + Marching Cubes -> 3D bone mesh
    -> interactive viewer (drag to rotate, anatomical preset views).

Pre-operative and post-operative CT can each be loaded and reconstructed
independently, then compared in the same 3D scene.
"""

__version__ = "0.1.0"
