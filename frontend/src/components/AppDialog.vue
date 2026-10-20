<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import AppIcon from './AppIcon.vue'
const props = defineProps<{ open: boolean; title: string }>()
const emit = defineEmits<{ close: [] }>()
const dialog = ref<HTMLDialogElement>()
function sync() { if (props.open && !dialog.value?.open) dialog.value?.showModal(); else if (!props.open && dialog.value?.open) dialog.value.close() }
watch(() => props.open, sync)
onMounted(sync)
</script>
<template><dialog ref="dialog" class="app-dialog" aria-labelledby="dialog-title" @cancel.prevent="emit('close')" @click="($event.target === dialog) && emit('close')"><div class="dialog-header"><h2 id="dialog-title">{{ title }}</h2><button class="icon-button" aria-label="Close dialog" autofocus @click="emit('close')"><AppIcon name="x"/></button></div><div class="dialog-content"><slot /></div></dialog></template>
