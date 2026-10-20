# HumanTwin frontend

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

- **Body explorer:** starts with Eyes selected and the first question. Click another body area, or use the six accessible buttons below the model. Supported regions: eyes, head, chest, abdomen, arms, and legs.
- **3D mode:** the bundled textured Rocketbox human has a full skeleton and subtle breathing/idle animation. Pause motion freezes the pose; app and OS reduced-motion preferences also freeze animation. Drag to rotate, scroll or pinch to zoom, or use + / −. Focus the viewer and use Left / Right arrows to rotate, + / − to zoom. Front, Back, Left side, Right side, and Reset move smoothly to a known view. Selection uses bone-attached raycast zones that follow skeletal animation, highlights the selected region, and displays its name beside the actual projected region. The eyes are selectable from the front; selecting Eyes from the buttons returns the camera to the front.
- **2D mode:** click the SVG regions; drag to pan; scroll or use + / − to zoom. Front / Back changes the anatomical side. Reset restores the front and clears pan and zoom. The region buttons provide a keyboard alternative in both modes.
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
