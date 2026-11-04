# HumanTwin frontend

The current 3D presentation uses the detailed textured Rocketbox human, a MakeHuman CC0 iris texture with shaped 3D eye surfaces, and seven bundled BodyParts3D regional reference models. Source/licence details and rebuild scripts are recorded in [ASSET_ATTRIBUTIONS.md](ASSET_ATTRIBUTIONS.md). These remain reference representations rather than scans of the study subject.

For the native-free local preview used on this Windows machine, run `npm run build:portable`, then `npm run preview:eye`. Open `http://127.0.0.1:5174/#twin` for the 3D person and observation model, or `http://127.0.0.1:5174/#eye-chat` for the eye surface and interview. `npm run test:realism` checks asset integrity and geometry; `npm run test:realism:browser` checks the running preview.

A responsive frontend for the **Intelligent Digital Twin of the Human Body**, based on the provided white, navy, and teal design reference. The AI chat calls the Laravel API and Python service. The separate Scripted demo mode uses mock responses. See the project-root README for full-stack setup and missing provider credentials. **This is a demonstration, not a medical diagnosis.**

## Install and run

Use **Node.js 22.12+ (22 LTS) or Node.js 24+** and npm.

From the project root:

```powershell
cd frontend
npm install
npm run dev
```

Open http://127.0.0.1:5173, or the alternative port Vite prints if that port is occupied. The Scripted demo needs no API key or backend. AI chat needs the Laravel and Python services described in the project-root README; the human model is already bundled. Dependencies are bundled locally; the app does not use external fonts or a CDN at runtime.

```powershell
npm run build
npm run preview
```

`build` checks TypeScript and produces the static site in `dist/`. Preview normally runs at http://127.0.0.1:4173. Host the contents of `dist/` on any static web host. Sites deployment metadata lives in `.openai/hosting.json`; it is not needed for local development or other hosting.

## Using the demo

- **Body explorer:** starts at the full body with Eyes selected in the symptom panel. Click the body or any of the six area buttons to animate into a detailed model. Use Back to full body or Escape to return. Supported regions: eyes, head, chest, abdomen, arms, and legs. Eyes, Arms and Legs have patient-left/right selection.
- **3D mode:** the full-body Rocketbox human has a skeleton and subtle breathing/idle animation. Pause motion or reduced motion freezes animation. Drag to rotate and scroll/pinch to zoom. Full-body Front, Back, Left side, Right side and Reset provide known views. Selection uses animated bone-bound raycasts, highlights the area and opens the detail viewer. Detailed anatomy uses actual 3D meshes, free orbit, bounded pan, zoom, Reset View and optional Auto Rotate. Keyboard controls are described below.
- **2D mode:** the full-body SVG supports area selection, pan/zoom and Front/Back. Selecting a region opens its anatomical illustration with Front, Side and Cross-section views. Drag/arrows pan and scroll/pinch/+/- zoom. The selected part, patient side and symptom draft survive switching between 2D and 3D.
- **Conversation:** choose an answer or enter your own text (up to 500 characters). For example: Eyes → My eyes hurt → Both eyes → A few days → Comes and goes. The five indicators cover the initial symptom prompt, location, onset, pattern, and completion. The pain slider updates the live summary from 1 to 10. After completion, the text input adds notes.
- **Summary:** Save stores a complete assessment locally. Export downloads a JSON record with the demonstration disclaimer. Changing the pain level or adding a note allows saving the updated record again.
- **Overview:** a guided starting page with direct links to all body areas.
- **Assessments / History:** browse saved records, search symptoms, filter by area, open a summary, export, or delete a record. History displays the same records as a timeline. Browser-local dates use the viewer’s timezone.
- **Settings:** choose whether new saves persist between visits, reduce motion, clear local history, or simulate a failure of the next assistant response. A simulated failure preserves the answer and presents Retry response. Switching areas cancels a pending response.
- **New assessment / × on the area chip:** clears the current in-memory conversation and opens the empty state. Existing saved records remain available.
- **Help / Guest:** opens instructions and local guest preferences. There is no account or authentication system.

## Loading, empty, and error states

The app shows model download progress, a retryable model/rig error state, delayed mock response indicators, empty conversation and history states, no-results filters, input validation, and retryable response failures. If WebGL2 is unavailable or its context is lost, the viewer offers retry and the SVG fallback. Storage errors display a recovery message and allow JSON export. Settings can clear corrupt local history.

Modern browsers with WebGL2 support can use the 3D viewer. The SVG view works without WebGL. The human is a clothed avatar with skin textures and natural proportions, not a medically validated anatomical model. See [asset attribution](ASSET_ATTRIBUTIONS.md).

## Source organization

```text
src/
  components/          # Reusable viewer, assistant, summary, navigation, dialogs, screens
    Body2D.vue         # Original interactive SVG, pan/zoom and front/back
    HumanBodyViewer.vue # Reusable GLTFLoader/OrbitControls/AnimationMixer viewer
  composables/
    useAssessment.ts   # Conversation state, cancellation, validation, retry and summaries
  data/
    regions.ts         # Body areas, answer options and region-specific prompts
  services/
    mockSymptomService.ts          # Delayed scripted responses; no API calls
    localAssessmentRepository.ts   # Validated localStorage access and settings
  three/
    humanViewerConfig.ts # Asset URL, bone mapping and camera presets
    buildHumanRig.ts    # Skeletal idle animation, selection zones and highlights
    disposeScene.ts     # GPU, texture, image bitmap and skeleton cleanup
  types.ts             # Shared region, message, assessment and service contracts
  App.vue              # Screen orchestration and local saves/exports
  style.css            # Tailwind import/theme and responsive component styling
tests/
  unit/                # Conversation contracts, error retry, stale response cancellation
  e2e/                 # Browser workflows, SVG/3D selection, fallback, mobile navigation
```

## Laravel / Python integration

The live boundary is now implemented. AI mode uses useAiAssessment, aiApi, AiSymptomAssistant, AiAssessmentSummary and AiHistoryView. The Vite proxy forwards /api and /sanctum to Laravel on port 8000. Python on port 8001 is private to Laravel. Credentials stay in server environments. The original useAssessment and mockSymptomService serve only the explicitly selected Scripted demo.

See ../README.md for authentication, consent, data isolation, provider configuration, rules and verification. Full-stack browser tests require both services and deliberately use AI_PROVIDER=disabled; provider doubles occur only in tests.

## Data and privacy

In AI mode, answers are sent to Laravel and Python and, when explicitly enabled, the configured AI provider. Saving health content requires separate consent. AI draft content is not saved in browser storage. The following local-storage details apply only to the Scripted demo: Draft conversations live in memory and reset on reload. Saved assessments (maximum 50) and display preferences use browser localStorage. Turning Remember assessments off makes new saves session-only; existing persisted history is retained until explicitly cleared. Clear history removes both persisted records and session records. Exports are downloaded to your device. This demo is intended for mock inputs.

## Verification

```powershell
npm run typecheck
npm test
npx playwright install chromium
npm run test:e2e
```

Playwright starts Vite automatically, or reuses the development server at port 5173. Tests cover a complete eye assessment, live pain summary, local persistence after reload, export, deletion, all six SVG selections, 3D raycast selection, rotation, WebGL context loss and 2D fallback, retry without duplicated messages, cancellation on region change, mobile navigation, settings, and help. Browser screenshots and failure traces go into the ignored `test-results/` directory.

Optional preview capture, with the dev server running:

```powershell
node scripts/capture-preview.mjs
```

Implementation references: [Vue](https://vuejs.org/guide/), [Tailwind CSS Vite integration](https://tailwindcss.com/docs/installation/using-vite), [Three.js OrbitControls](https://threejs.org/docs/pages/OrbitControls.html), [Three.js Raycaster](https://threejs.org/docs/pages/Raycaster.html).


## Realistic human viewer

`HumanBodyViewer.vue` accepts `selected`, `view` (front/back/left/right), `zoom`, `reducedMotion`, optional `paused`, and an optional `modelConfig`. It emits `select`, `ready`, `progress`, `error`, `orientation`, and `zoom`. Selection events use the existing `RegionId` contract, so all six areas continue to open their existing mock questionnaires. The component loads the local GLB with GLTFLoader, animates its skeleton with AnimationMixer, and attaches hidden raycast zones and translucent selection highlights to the matching bones. Labels track projected animated anchors. Mouse/touch drags and pinches do not submit accidental body clicks.

The original procedural mannequin has been removed. The bundled model is Microsoft Rocketbox Male_Adult_01 (MIT), in a shirt and shorts. All skin/clothing textures are embedded in `public/models/human.glb` (about 3 MB). Nothing is missing. It is not a scan of the user or a clinical anatomy model. See `public/models/README.md` for replacing the avatar, bone mapping, supported GLTF formats, and rebuilding the asset. Preserve the bundled Microsoft MIT notice when distributing it.

The viewer uses environment/key/fill lighting, contact and directional shadows, responsive camera fitting and eased camera transitions. Offscreen/hidden viewers pause rendering and animation. Unmount stops the frame loop, cancels requests, disconnects observers/listeners, stops/uncaches the mixer, and disposes geometries, materials, textures, image bitmaps, bone textures, environment maps, controls and the WebGL context. Late model loads are discarded. No backend or AI API was added; the existing `SymptomService` and repository boundaries remain ready for Laravel/Python integration.

Browser coverage in `tests/e2e/human-viewer.spec.ts` checks real GLB loading, skin textures, skeleton deformation, animation-following anchors, pause/resume, all six body raycasts and eye questionnaire completion, side/back/front transitions, drag rotation, button/wheel zoom, model loading progress, missing-model retry, repeated unmount/remount, and mobile touch selection/rotation with reduced motion. The existing browser suite also checks WebGL context loss and 2D fallback.
## Body-part exploration

The explorer opens in the full-body view with the local **Scripted demo** symptom assistant selected by default. An existing session's explicit AI-mode preference is respected. Click the model or any area button to open its detail view. The opening uses a 620 ms camera move and 420 ms detail reveal (1,040 ms total), skipped for reduced-motion preferences. Escape or **Back to full body** returns to the body without clearing the symptom conversation.

**3D:** drag to orbit through 360°, scroll/pinch or use +/− to zoom, right-drag/two-finger drag to pan. Arrow keys orbit, Shift+arrows pan, R/Home or **Reset View** resets. **Auto Rotate** is optional and suppressed for reduced motion. **2D:** drag/two-finger drag or arrows pan, pinch/scroll/+/- zoom, R/Home resets. Front, Side and Cross-section show distinct original illustrations; there is no 3D rotation in 2D. Left/right always refers to the patient's perspective. Mode switching keeps the selected area, side, transcript, pain and typed draft.

`src/data/bodyParts.ts` maps labels, laterality, lazy model factories or GLB URLs, illustration URLs and camera settings. `BodyViewer.vue` manages the opening/return lifecycle, `BodyPartViewer.vue` supplies shared UI and loading/error handling, and `BodyPart3D.vue` / `AnatomyIllustration.vue` provide the interaction engines. Detail geometry is loaded only after a selection. The existing full-body scene is retained for return and its rendering pauses while hidden. Detailed scenes release GPU resources on mode changes/unmount. Requests and mock replies remain in existing service adapters; Laravel and Python contracts are unchanged. Optional demo-side metadata is included in exported snapshots.

The bundled detailed assets are original **schematic educational anatomy**, including real eye geometry and a generated radial iris texture. They are not clinically validated. See [ASSET_ATTRIBUTIONS.md](ASSET_ATTRIBUTIONS.md) for sources, MIT notices, reproducible artwork generation, and the precise reviewed assets needed for a clinical atlas. No remote model or texture service is required.

Verify with `npm run build`, `npm test`, and `npx playwright test`. `tests/e2e/body-part-detail.spec.ts` verifies the requested full-body → Eyes → animated eye → rotate/zoom → 2D → full-body flow, all regions, error recovery, touch and reduced motion. Full-stack AI tests skip when Laravel/Python are unavailable.
