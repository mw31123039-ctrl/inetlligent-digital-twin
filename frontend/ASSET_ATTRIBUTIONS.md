# Asset provenance and attribution

Updated 1 November 2026. These are reference representations, not a reconstruction of the study subject or a claim of clinical validation.

## Textured 3D human

The active avatar is `public/models/human-detailed.glb`, derived from **Male_Adult_01** in the [Microsoft Rocketbox Avatar Library](https://github.com/microsoft/Microsoft-Rocketbox/tree/0943055db6ec570bcef9f2c8b41c9e5467c808f9/Assets/Avatars/Adults/Male_Adult_01), revision `0943055db6ec570bcef9f2c8b41c9e5467c808f9`.

Copyright (c) 2020 Microsoft. **MIT license**; the complete notice remains bundled at [public/models/LICENSE-Rocketbox.txt](public/models/LICENSE-Rocketbox.txt) and is copied into builds.

The original `human.glb` is retained. Its FBX conversion preserves the highest-detail mesh, original UVs and skeleton, with 1024px body/head/opacity colors. `scripts/prepare-human-model.mjs` documents that conversion. The new `scripts/prepare-human-realism.mjs` adds the pinned original **2048px head color and head/body normal maps**, preserves the rig and UV layout, and adjusts PBR roughness. Source pixels are encoded losslessly as embedded PNGs with the original export orientation. Source/output hashes and dimensions are in `human-detailed.manifest.json`.

The application creates its own subtle skeletal breathing/idle clip from the rig and lowers the arms into a standing posture. No additional third-party animation is used. Both Body explorer and Patient twin load the actual skinned 3D model; Patient twin no longer defaults to its earlier SVG figure. The reference adult is not a scan or likeness of the study subject.

## Regional anatomical reference geometry

Non-eye 3D close-ups now load **BodyParts3D 4.0 reference mesh geometry**. Sources: the [official download page](https://dbarchive.biosciencedbc.jp/en/bodyparts3d/download.html), the IS-A 99% polygon-reduced OBJ archive, and official IS-A/PART-OF concept tables.

Required attribution: **BodyParts3D, © The Database Center for Life Science licensed under CC Attribution 4.0 International**.

The [current official archive license page](https://dbarchive.biosciencedbc.jp/en/bodyparts3d/lic.html), updated 27 February 2025, specifies [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Historical third-party descriptions can mention an earlier license; this preparation records the official archive license used for this download. Visible credit/license links appear below the 3D viewer. Distributed notices and source details are in `public/models/anatomy/ATTRIBUTION.txt` and `manifest.json`.

| Files | Reference anatomy |
| --- | --- |
| head.glb | Brain, cerebellum and brainstem |
| chest.glb | Heart, lungs, trachea, sternum and 24 ribs |
| abdomen.glb | Liver, stomach, intestines and kidneys |
| arms-left.glb, arms-right.glb | Sided humerus, radius, ulna and biceps heads |
| legs-left.glb, legs-right.glb | Sided femur, tibia, fibula, patella and gastrocnemius heads |

`scripts/prepare-reference-anatomy.mjs` fetches selected ZIP entries with HTTP ranges, verifies their size/CRC, and records individual SHA-256 and FMA/FJ identifiers. **598 source elements** are prepared across seven GLBs. Duplicate position vertices are welded and smooth normals are recomputed; surface positions and triangle topology are retained. Source Z-up coordinates are rotated to Y-up, with anterior -Y mapped to +Z, and uniformly centered/scaled within each region. Colors, mild vertex variation and material response are illustrative. Ribs are translucent to reveal the organs.

Left/right files retain the corresponding published source elements. Some IDs carry an `M` suffix; these remain as published. Separate output files do not establish independently measured left/right anatomy or patient asymmetry. Regional scaling preserves proportions within that model, not a common physical scale across viewers. The manifest records source elements, archive ETag, transforms, triangle counts and output hashes.

These are reference anatomical surfaces, not an application-reviewed clinical atlas or patient scans. Geometry, colors, orientation, labels and completeness still require specialist review before clinical use. The earlier original sphere/tube organ artwork remains in the repository but is no longer the default regional source.

## Eye surface and internal layers

`src/eye/naturalEye.ts` contains original 3D presentation geometry for shaped lids/skin, tapered lashes, canthi, tear margin, sclera, limbus, recessed optical chamber, iris ring and clear cornea. PBR materials, a local studio environment and an eyelid visibility mask provide the surface presentation. The pupil remains a genuine opening with a narrow border and invisible selection target. Isolating a structure disables its lid visibility mask.

The iris samples the **unchanged MakeHuman core `brown_eye.png`** through mesh UV coordinates. Source revision: `a8bc2d54ff0ac92e78ff71431b1023eda42bf482`; original path: `makehuman/data/eyes/materials/brown_eye.png`.

MakeHuman's [official license page](https://www.makehumancommunity.org/about/license.html) states that core graphics assets are **CC0**. The adjacent source `brown.mhmat` explicitly records the September 2020 CC0 release and its copyright holders: Data Collection AB, Joel Palmius and Jonas Hauquier. The unmodified PNG, material declaration, root license explanation, revision, hashes and attribution are retained in `public/textures/eye/`. This uses a core graphic asset, not MakeHuman application source code. Recreate it with `node scripts/prepare-eye-texture.mjs`.

Surface view opens first in compact and full eye workspaces. All 63 anatomy IDs and existing internal/magnified views remain available. Internal geometry, exploded spacing and microscopic layers remain schematic. Optical settings are illustrative, not a validated optical model or participant biometric measurement. A reference eye texture does not make the eye patient specific.

## Original fallback artwork and libraries

- The accessible 2D body remains the original SVG in `src/components/Body2D.vue`.
- Eighteen original regional front/side/section SVGs remain in `public/illustrations/`, under its distributed MIT notice. Rebuild with `scripts/prepare-anatomy-illustrations.mjs`. They remain schematic fallbacks.
- Original procedural eye/organ artwork and the new eye surface geometry are project work under `public/illustrations/LICENSE.txt`; third-party geometry and textures retain their own licenses above.
- HumanTwin mark and favicon are original SVG artwork. The historical user-supplied design-reference attachment is not redistributed.
- Three.js/OrbitControls: MIT, the Three.js authors, [threejs.org](https://threejs.org/).
- Lucide: ISC, with retained MIT notices for Feather-derived portions, [lucide.dev](https://lucide.dev/).
- Vue, Vite and Tailwind CSS retain their installed licenses. `package-lock.json` records exact versions.

Keep all model/data notices with redistributed assets. Source assets are prepared at development time; the running application loads its bundled models and textures locally.

## Chest organ-surface view: Z-Anatomy

The chest's default **Organ surfaces** view is a separate reference asset, `public/models/anatomy/chest-surface.glb`, selected from [Z-Anatomy's published FBX models](https://github.com/LluisV/Z-Anatomy/tree/6c7f9016bd5899ac8edafd31b9900c151df42ed6/Resources/Models/FBX). Credit: **Lluís Vinent Juanico and contributors; Z-Anatomy by Gauthier Kervyn; BodyParts3D / DBCLS**. The source project declares [CC BY-SA 4.0](https://github.com/LluisV/Z-Anatomy/blob/6c7f9016bd5899ac8edafd31b9900c151df42ed6/LICENSE).

This derivative model asset is distributed under **CC BY-SA 4.0**, separately from application code and the CC BY 4.0 BodyParts3D models. Its full source license and attribution are retained as `LICENSE-Z-Anatomy.txt` and `ATTRIBUTION-Z-Anatomy.txt`, with detailed provenance in `chest-surface.manifest.json`. Retain these notices and the same asset license when redistributing this adapted model.

Only **18 explicitly named meshes** are included: five lung lobes, trachea/main bronchi, four heart chambers and selected great/coronary vessels. Source files are `VisceralSystem100.fbx` and `CardioVascular41.fbx`, pinned at revision `6c7f9016bd5899ac8edafd31b9900c151df42ed6`. Their original world transforms are retained together, vertices are welded and smooth normals recomputed, illustrative materials are assigned, and the selection is uniformly scaled/centered for GLB export. Unrelated organs, annotation markers and source textures are excluded; the complete source FBXs are not redistributed. Rebuild with `node scripts/prepare-chest-surface.mjs`.

The separate **Vessels and ribs** view retains the BodyParts3D model and its own attribution. The historical BodyParts3D lung aggregate mainly describes pulmonary branches; it is not presented as a complete outer lung surface. Both views are educational reference anatomy and still require specialist review before clinical use.
