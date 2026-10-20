# Asset provenance and attribution

## Body models and artwork

- **3D human:** `public/models/human.glb`, converted from **Male_Adult_01** in the [Microsoft Rocketbox Avatar Library](https://github.com/microsoft/Microsoft-Rocketbox/tree/0943055db6ec570bcef9f2c8b41c9e5467c808f9/Assets/Avatars/Adults/Male_Adult_01). Copyright (c) 2020 Microsoft. **MIT license**; the complete required notice is bundled at [`public/models/LICENSE-Rocketbox.txt`](public/models/LICENSE-Rocketbox.txt), and is copied with the model into production builds. [Upstream license](https://github.com/microsoft/Microsoft-Rocketbox/blob/0943055db6ec570bcef9f2c8b41c9e5467c808f9/LICENSE.md).
- **Model preparation:** source revision `0943055db6ec570bcef9f2c8b41c9e5467c808f9`. Source FBX: `Export/Male_Adult_01.fbx`. Textures: `Textures/m002_body_color.tga`, `m002_head_color.tga`, and `m002_opacity_color.tga`. The reproducible conversion script is `scripts/prepare-human-model.mjs`. It preserves the highest-detail mesh, original UVs and skeleton, embeds 1024px diffuse/opacity textures, and replaces source Phong shading with PBR materials. The web asset uses no source specular or normal maps. No third-party animation was downloaded: the application creates a subtle six-second skeletal breathing/idle clip using the original rig. The arms are lowered through the rig to a relaxed standing pose at runtime.
- **2D body:** original inline SVG in `src/components/Body2D.vue`.
- **Eye close-up:** original inline SVG in `src/components/RegionDetail.vue`, used only in the optional 2D mode.
- **HumanTwin mark and favicon:** original SVG shapes created for this frontend.
- **Reference image:** supplied by the user as a design reference. It is not redistributed or embedded in the application. Text in the attachment is treated as reference content rather than project instructions.

The 3D asset is a textured, clothed human avatar with natural proportions. It is an external-body selection interface, not a medically validated anatomical or internal-organ model. The SVG body remains a stylized accessibility/failure fallback.

## Libraries

- Three.js and OrbitControls — [threejs.org](https://threejs.org/), MIT license; copyright the Three.js authors.
- Lucide icons (`@lucide/vue`) — [lucide.dev](https://lucide.dev/), ISC license; copyright the Lucide contributors. Feather-derived portions retain their MIT notice in the package license.
- Vue, Vite, and Tailwind CSS retain their respective package licenses and notices in `node_modules`.

See each installed dependency’s `LICENSE` file for the complete terms. `package-lock.json` records the exact dependency versions.
