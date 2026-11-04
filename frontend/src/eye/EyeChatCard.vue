<script setup lang="ts">
import { inject } from 'vue'
import { createEyeContext,eyeContextKey } from './context'
import EyeInterview from './EyeInterview.vue'
const eye=inject(eyeContextKey)||createEyeContext()
defineEmits<{details:[]}>()
</script>
<template><div class="panel eye-inline-assistant" :dir="eye.session.locale==='en'?'ltr':'rtl'" :lang="eye.session.locale" tabindex="-1" data-testid="inline-eye-assistant">
 <div class="eye-inline-context"><span>{{eye.session.model_side==='left'?'Left':'Right'}} eye model · {{eye.session.reported.laterality==='unknown'?'reported side not set':`reported: ${eye.session.reported.laterality}`}}</span><button @click="$emit('details')">3D anatomy &amp; saved summary ↗</button></div>
 <EyeInterview :session="eye.session" :acknowledged="eye.acknowledged.value" compact @answer="eye.answer" @acknowledge="eye.acknowledged.value=$event" @reset="eye.reset"/>
 <p v-if="eye.error.value" class="eye-error" role="alert">{{eye.error.value}}</p>
</div></template>
