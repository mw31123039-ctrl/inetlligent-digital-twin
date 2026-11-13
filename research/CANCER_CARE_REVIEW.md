# HumanTwin cancer care: source review and implementation

Sources consulted: 13 November 2026. This is a development research review, not independent clinical peer review or certification of medical accuracy.

## Clinical reasoning behind the workflow

Cancer investigation is a process involving medical history, examination and suitable tests. Imaging, laboratory findings and pathology supply different evidence. A photograph cannot establish every cancer, a reassuring model category cannot exclude disease, and cancer treatment cannot be selected from an image class alone. The [National Cancer Institute diagnosis guide](https://www.cancer.gov/about-cancer/diagnosis-staging/diagnosis) supports the distinction between assessment, imaging and tissue diagnosis. Its [treatment overview](https://www.cancer.gov/about-cancer/treatment/types) explains why treatment depends on the confirmed disease and its extent.

The workspace now separates three activities:

1. **Analyze an image:** choose a compatible installed model, prepare a permitted image, confirm processing and inspect actual computed findings.
2. **Cancer knowledge:** browse or ask the local semantic model to retrieve relevant records from a curated primary-source collection.
3. **Care and next steps:** prepare an educational clinical-review checklist containing reported context, possible investigations, general treatment approaches and source links. It does not order tests, establish a stage, prescribe medication or decide treatment.

The digital body remains a reference representation. It is not a device that scans a person or infers hidden diseases from the avatar. The matching study code links the exported review with the existing twin; the strict physiological-observation schema is not populated with unvalidated cancer diagnoses.

## Breadth and sources

The shared [source corpus](../contracts/cancer-knowledge.v1.json) covers 16 topics: skin, oral cavity, lung, breast, colorectal, prostate, cervical, ovarian, pancreatic, liver, kidney, adult central nervous system, bladder, thyroid, leukaemia with an AML reference, and lymphoma with a non-Hodgkin reference. The corpus also includes four records explaining uploads, model scores, treatment decisions and urgent concerns.

Every cancer topic includes source-linked information about reported changes, clinical investigations, treatment categories and the relevant specialty. Specific source scope matters: the AML and non-Hodgkin summaries are not substitutes for the many other blood-cancer subtypes. Topics without a trained image model are labelled as knowledge guides, not working image detectors.

[The source-verification snapshot](cancer-source-review.json) records 29 primary NCI/NHS URLs, resolved page titles, HTTP status and page hashes. All 29 were accessible when checked. The snapshot verifies the referenced pages and supplies provenance; it does not establish clinical entailment, future currency, professional approval or patient-level performance. Recheck with `node research/verify-cancer-sources.mjs`. Only metadata is stored, not copies of complete source pages.

Urgent-concern information is based on [NHS breathing-difficulty guidance](https://www.nhs.uk/symptoms/shortness-of-breath/), [bleeding guidance](https://www.nhs.uk/conditions/cuts-and-grazes/) and [coughing-up-blood guidance](https://www.nhs.uk/symptoms/coughing-up-blood/). The app uses a location-neutral instruction to seek local emergency care. Its short checklist is not comprehensive triage. Unchecked boxes do not establish symptom absence. Previously reported emergency concerns remain visible until the case is cleared, and the image button cannot silently downgrade them.

## Actual local AI

Four existing learned image classifiers remain active: dermoscopy ViT, breast-ultrasound ViT, lung CT-slice EfficientNet-B0 and locally trained oral-lesion ResNet18. Their exact training sources, fingerprints, conversion checks and limited image-level evaluation are documented in [the service guide](../ai-service/README.md#cancer-research-models).

The new knowledge AI uses [all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2), through a [pinned ONNX export](https://huggingface.co/Xenova/all-MiniLM-L6-v2/tree/751bff37182d3f1213fa05d7196b954e230abad9). It is an Apache-2.0 general sentence encoder, not a medically validated language model. Its model weights and tokenizer are fingerprinted. Attention-masked mean pooling and L2 normalization follow the source model documentation. The service computes real vectors for the 20 curated records and compares a question with them using cosine similarity.

The model returns only closed, approved record IDs and measured relevance values. Medical prose is rendered from the shared corpus. It cannot add arbitrary diagnoses, medicines, numerical cancer probabilities, treatment doses or invented citations to its response. Relevance values are not disease likelihoods. The software threshold for finding a nearby record is not a clinically validated threshold. Limited coverage, English-language assumptions and imperfect retrieval remain limitations; users can inspect original sources and browse the library even when AI search is unavailable.

No claim is made that adding reference records retrains the image classifiers, creates a universal medical model, or validates clinical reasoning. Semantic retrieval supplements the separate image models.

## Interface and image preparation

The new HumanTwin logo is an original project-native SVG mark. It is used in the header and favicon and remains sharp at different sizes. The cancer workspace uses a new sage, cream and dark-green visual system. Main copy is normally 17 pixels; essential labels and controls are generally 16–17 pixels. The shared header/sidebar are enlarged, and the A+ control supports a larger type preference without storing health content.

Upload is available from the first screen and the image area. JPEG/PNG files up to 16 MB are inspected for dimensions before decoding. Source limits are 8192 pixels per side and 40 megapixels. Larger permitted images are scaled proportionally to fit a 2048-pixel prepared side and re-encoded to JPEG within the existing service limit. An extreme crop is rejected instead of being stretched to meet a minimum dimension. Original and prepared dimensions are retained in consented exports. The user must still confirm the input type; these technical checks do not verify anatomy or clinical image quality. DICOM, PDFs and full scan volumes are not silently interpreted as photos.

Two oral examples are redistributed under CC BY 4.0 with [attribution and transformation details](../frontend/public/cancer-examples/ATTRIBUTION.md). They are source-labelled research references, not images of the user. Loading an example does not automatically grant processing permission, and its label is not a guarantee that the classifier will return that label.

## Privacy and verification

Questions require authentication and explicit local-processing permission. Laravel forwards only the question and permission flag to private Python; it adds the existing internal service credential. Names, account identity and study codes are not forwarded to the encoder. Question text is not saved, used for training or sent to an external AI provider. Existing access-log suppression and no-store response headers apply. UI research notes, examples and findings remain in page memory unless the user explicitly downloads a case. Browser file metadata removal does not remove names visible in image pixels.

Laravel validates the closed retrieval schema and question fingerprint independently. Vue verifies version, question binding, record IDs, duplicates, privacy flags and finite relevance values before using any match. Missing/corrupt encoder artifacts return an unavailable state; no placeholder answer is presented as AI output. Model activation and record retrieval are software checks, not evidence of medical safety.

Meaningful checks cover actual local semantic retrieval, missing/corrupt inputs, unknown records, question binding, consent, authentication, no health-record writes, emergency precedence, image-header bounds, safe resizing, large text, source navigation, public examples and all four real image-model uploads. Browser screenshots and runtime reports are in the ignored `frontend/test-results/cancer-care` and `cancer-real` folders. Independent patient-level, clinical and usability evaluation would still be needed before any real care deployment.
