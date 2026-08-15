---
name: contech-cad-vision
description: Extract geometric entities, coordinates, layers, and cross-sections from .DWG, .DXF, and vectorized PDF drawing sets for civil & structural engineering automation.
---
# ConTech CAD Vision Skill

**Goal**: Ingest multi-layer CAD drawing sets and extract precise geometric line segments, polylines, coordinates, and textual callouts without generative hallucination.

## Workflow:
1. **Entity Extraction**: Parse DXF/DWG vector geometry using `ezdxf` and geometry classifiers.
2. **Layer Categorization**: Map CAD layers against company standards (e.g. `S-CONC`, `C-ROAD-ASPH`, `M-PIPE`).
3. **Annotation & Dimension Matching**: Link spatial OCR text (e.g. `Ø16 @ 200mm c/c`, `T.O.C. +4.50m`) directly to bounded geometric entities.
4. **Validation**: Enforce coordinate bounding checks and cross-sectional elevation consistency.
