<script setup lang="ts">
import AppIcon from './AppIcon.vue'
import type { AiChatState } from '../types/ai'
defineProps<{ state: AiChatState }>()
defineEmits<{ open: [id: string]; remove: [id: string]; explore: []; refresh: [] }>()
</script>
<template>
  <section class="panel ai-summary">
    <div class="ai-summary-heading"><h2>Saved AI conversations</h2><button v-if="state.user && state.savedChats.length" class="button-secondary" @click="$emit('refresh')">Refresh saved conversations</button></div>
    <div v-if="!state.user" class="history-empty"><span class="empty-icon"><AppIcon name="user" :size="30"/></span><h2>Sign in to see saved conversations</h2><p>Conversations are saved to your account only when you choose to, and you can delete them at any time.</p><button class="button-primary" @click="$emit('explore')">Open body explorer<AppIcon name="arrowRight" :size="17"/></button></div>
    <div v-else-if="!state.savedChats.length" class="history-empty"><span class="empty-icon"><AppIcon name="clipboard" :size="30"/></span><h2>No saved conversations yet</h2><p>Finish an AI symptom conversation and choose to save it. Saving health information always asks for your consent first.</p><div class="ai-history-empty-actions"><button class="button-primary" @click="$emit('explore')">Start in the body explorer<AppIcon name="arrowRight" :size="17"/></button><button class="button-secondary" @click="$emit('refresh')">Check again</button></div></div>
    <template v-else>
      <div v-for="record in state.savedChats" :key="record.id" class="ai-history-record"><div><strong>{{ record.region }} conversation</strong><p>{{ new Date(record.created_at).toLocaleString() }}</p></div><button class="button-secondary" @click="$emit('open', record.id)">View saved summary</button><button class="ai-text-button" :aria-label="`Delete saved ${record.region} conversation`" @click="$emit('remove', record.id)">Delete</button></div>
      <button class="button-primary" @click="$emit('explore')">Open body explorer</button>
    </template>
    <p v-if="state.error" role="alert">{{ state.error }}</p>
  </section>
</template>
<style scoped>
.ai-history-empty-actions{display:flex;flex-wrap:wrap;justify-content:center;gap:8px;margin-top:8px}
</style>
