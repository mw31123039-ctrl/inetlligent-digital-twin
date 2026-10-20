# Bundled human model

`human.glb` is ready to use. No model downloads or API keys are required at runtime.

Source: [Microsoft Rocketbox, Male_Adult_01](https://github.com/microsoft/Microsoft-Rocketbox/tree/0943055db6ec570bcef9f2c8b41c9e5467c808f9/Assets/Avatars/Adults/Male_Adult_01), revision `0943055db6ec570bcef9f2c8b41c9e5467c808f9`.

Copyright (c) 2020 Microsoft. MIT license. Keep `LICENSE-Rocketbox.txt` with distributed copies. See `../../ASSET_ATTRIBUTIONS.md` for preparation details.

To replace the avatar, put a properly licensed textured, skinned GLB here and change `src/three/humanViewerConfig.ts`. A self-contained GLB is preferred; GLTF files must also include all referenced BIN and texture files. The loader currently accepts uncompressed standard GLTF 2.0; Draco/KTX2 assets need their matching decoders configured first. Use a standing, Y-up model facing +Z, and map the pelvis, spine, chest, neck, head, arm, hand, thigh, shin and foot bones. The supplied zone dimensions and facial offsets fit this Rocketbox adult; retune `src/three/buildHumanRig.ts` for another avatar, particularly eye targets. Set `idleClip` only for an in-place, steady clip; otherwise a breathing/idle clip is generated. Do not use a walk, dance, or root-motion clip for assessment selection.

Rebuild the supplied asset with the dev server running:

```powershell
node scripts/prepare-human-model.mjs
```

This uses the existing Playwright Chromium installation and downloads pinned source assets into the OS temporary directory. The finished GLB and MIT notice are written here. FBX/TGA source files are not required by the frontend.
