<script setup lang="ts">
import { computed, ref } from 'vue'
import HumanBodyViewer from '../components/HumanBodyViewer.vue'
import { humanModelConfig, type HumanView } from '../three/humanViewerConfig'
import type { RegionId } from '../types'
import type { PatientSide } from '../data/bodyParts'
import { useBodyDisplay } from './context'

defineProps<{ selected: RegionId | null; side?: PatientSide; view: HumanView; zoom: number; reducedMotion: boolean; paused?: boolean }>()
const emit = defineEmits<{ select: [id: RegionId, side?: PatientSide]; error: [message: string]; ready: []; progress: [value: number | null]; orientation: [value: HumanView]; zoom: [value: number] }>()
const body = useBodyDisplay(), viewer = ref<InstanceType<typeof HumanBodyViewer>>()
const config = computed(() => ({ ...humanModelConfig,
  kind: body.mode.value === 'realistic' ? 'reference' as const : body.mode.value,
  url: body.mode.value === 'personal' ? body.personalUrl.value : humanModelConfig.url,
  facingRotation: body.mode.value === 'personal' ? body.rotation.value : 0,
}))
defineExpose({ reset: () => viewer.value?.reset(), setView: (view: HumanView) => viewer.value?.setView(view), focusPart: (part: RegionId, side: PatientSide) => viewer.value?.focusPart(part, side) ?? Promise.resolve(), getSnapshot: () => viewer.value?.getSnapshot() })
</script>
<template>
  <HumanBodyViewer v-if="body.mode.value !== 'personal' || body.personalUrl.value" ref="viewer" :selected="selected" :side="side" :view="view" :zoom="zoom" :reduced-motion="reducedMotion" :paused="paused" :model-config="config" @ready="emit('ready')" @error="emit('error',$event)" @progress="emit('progress',$event)" @orientation="emit('orientation',$event)" @zoom="emit('zoom',$event)" @select="(id, patientSide) => emit('select',id,patientSide)"/>
  <div v-else class="personal-body-empty" role="status"><strong>Your own human model</strong><p>Use “Attach a GLB model” above to display a 3D scan or model you are permitted to use.</p><p>Your shape and appearance are for visualization. The model does not supply internal anatomy or medical measurements.</p></div>
</template>
