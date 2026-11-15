<script setup lang="ts">
import { ref, watch } from 'vue'
import { useBodyDisplay } from './context'
import './avatar.css'
const body = useBodyDisplay(), permitted = ref(false), error = ref('')
watch(body.account, () => { permitted.value = false; error.value = '' })
async function attach(event: Event) {
  const input = event.target as HTMLInputElement, file = input.files?.[0]
  input.value = ''; error.value = ''
  if (!file) return
  const scope = body.account.value
  try { await body.attach(file, permitted.value) } catch (cause) { if (scope === body.account.value) error.value = cause instanceof Error ? cause.message : 'The personal model could not be prepared.' }
}
</script>
<template>
  <div class="body-display-controls">
    <div class="body-display-heading"><strong>Your body view</strong><span>{{ body.account.value === 'guest' ? 'Guest preference on this browser' : 'Preference for this account on this browser' }}</span></div>
    <div class="body-display-options" role="group" aria-label="Choose body representation"><button v-for="item in ([['realistic','Reference person'],['anatomy','Organs & bones'],['personal','My 3D model']] as const)" :key="item[0]" :aria-pressed="body.mode.value === item[0]" @click="body.setMode(item[0]); error = ''">{{ item[1] }}</button></div>
    <div v-if="body.mode.value === 'personal'" class="personal-body-input">
      <p>Attach your own 3D scan or human model. The file stays in this tab and is cleared when you change accounts or reload.</p>
      <label class="personal-body-permission"><input v-model="permitted" type="checkbox"/>I own this model or have permission to use it.</label>
      <label class="personal-body-file" :class="{ disabled: !permitted || body.pending.value }">{{ body.pending.value ? 'Checking model…' : body.personalUrl.value ? 'Replace 3D model' : 'Attach a GLB model' }}<input type="file" accept=".glb,model/gltf-binary" aria-label="Attach personal 3D model" :disabled="!permitted || body.pending.value" @change="attach"/></label>
      <small>GLB · up to 40 MB · embedded PNG/JPEG textures · standing, Y-up human. A photograph is not a 3D scan.</small>
      <div v-if="body.personalUrl.value" class="personal-body-attached"><span>{{ body.fileName.value }}</span><button @click="body.rotation.value = (body.rotation.value + Math.PI / 2) % (Math.PI * 2)">Turn model 90°</button><button @click="body.clearPersonal()">Remove personal model</button></div>
      <p v-if="error" class="personal-body-error" role="alert">{{ error }}</p>
    </div>
  </div>
</template>
