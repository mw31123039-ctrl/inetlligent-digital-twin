# Bundled human model

The Body explorer and Patient twin now offer **Reference person**, **Organs & bones**, and **My 3D model**. The selected view is stored separately for each signed-in account (and guest) on this browser. A personal GLB is processed locally, kept in page memory and cleared on reload, account change or explicit removal. Its file, filename, fingerprint and object URL are never saved in browser preferences or uploaded by this feature. Personal models need permission from their owner and embedded PNG/JPEG textures; compressed meshes and external texture/buffer URLs are rejected. An imported appearance does not supply internal organs, measurements or diagnoses. Body-area locations on a personal surface are approximate.

The anatomy overview reuses the seven existing BodyParts3D assets. `src/three/anatomyOverview.ts` removes each regional model's display centering and scale while preserving the shared source-to-Y-up rotation, then combines the regions in their original common coordinate system. The result is normalized once for display. Organs are not independently fitted to arbitrary avatar body parts, and none of these reference structures are inferred from a personal scan. Existing regional source geometry, identifiers, hashes and attribution files are retained unchanged. This overview includes the selected published organs and bones, not every anatomical structure.

Run `npm test -- avatar.test.ts` and `node scripts/smoke-body-displays.mjs` from `frontend/` to check file admission, coordinate restoration, account isolation and the real browser flows. Browser screenshots use the licensed reference avatar as an explicit personal-file handling example, not a study subject's model.

The active model is now **`human-detailed.glb`**: the same licensed rig with original 2048px face color and face/body normal maps. Its source/output hashes are in `human-detailed.manifest.json`. From `frontend/`, rebuild with `node scripts/prepare-human-realism.mjs`; the original `human.glb` and MIT notice remain available.

The `anatomy/` folder contains seven prepared BodyParts3D regional reference models, including separate published left/right limb elements. Its `ATTRIBUTION.txt` and `manifest.json` carry CC BY 4.0 attribution, source IDs, transforms and hashes. Rebuild with `node scripts/prepare-reference-anatomy.mjs`. These reference models and the avatar are not scans of the study subject.

The default chest **Organ surfaces** view additionally uses `anatomy/chest-surface.glb`, an 18-mesh Z-Anatomy derivative under **CC BY-SA 4.0**. Retain `ATTRIBUTION-Z-Anatomy.txt`, `LICENSE-Z-Anatomy.txt` and `chest-surface.manifest.json` with it. Rebuild with `node scripts/prepare-chest-surface.mjs`. The alternative **Vessels and ribs** view uses the original BodyParts3D chest model. See the frontend asset-attribution document for source authors and license boundaries.

`human.glb` is ready to use. No model downloads or API keys are required at runtime.

Source: [Microsoft Rocketbox, Male_Adult_01](https://github.com/microsoft/Microsoft-Rocketbox/tree/0943055db6ec570bcef9f2c8b41c9e5467c808f9/Assets/Avatars/Adults/Male_Adult_01), revision `0943055db6ec570bcef9f2c8b41c9e5467c808f9`.

Copyright (c) 2020 Microsoft. MIT license. Keep `LICENSE-Rocketbox.txt` with distributed copies. See `../../ASSET_ATTRIBUTIONS.md` for preparation details.

To replace the avatar, put a properly licensed textured, skinned GLB here and change `src/three/humanViewerConfig.ts`. A self-contained GLB is preferred; GLTF files must also include all referenced BIN and texture files. The loader currently accepts uncompressed standard GLTF 2.0; Draco/KTX2 assets need their matching decoders configured first. Use a standing, Y-up model facing +Z, and map the pelvis, spine, chest, neck, head, arm, hand, thigh, shin and foot bones. The supplied zone dimensions and facial offsets fit this Rocketbox adult; retune `src/three/buildHumanRig.ts` for another avatar, particularly eye targets. Set `idleClip` only for an in-place, steady clip; otherwise a breathing/idle clip is generated. Do not use a walk, dance, or root-motion clip for assessment selection.

Rebuild the supplied asset with the dev server running:

```powershell
node scripts/prepare-human-model.mjs
```

This uses the existing Playwright Chromium installation and downloads pinned source assets into the OS temporary directory. The finished GLB and MIT notice are written here. FBX/TGA source files are not required by the frontend.
