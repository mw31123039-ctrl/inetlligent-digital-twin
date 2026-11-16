<script setup lang="ts">
import { computed, ref } from 'vue'
import { chartRows } from '../dental/model'
import { nodeLabel, regionOf, sideChoices } from './anatomy'
import { translate, type StringKey } from './i18n'
import type { AnatomyNode, ClinicalCatalog, ClinicalLocale, ClinicalSide } from './types'

const props = defineProps<{ catalog: ClinicalCatalog; nodes: Map<string, AnatomyNode>; selectedId: string; side: ClinicalSide; locale: ClinicalLocale; locked: boolean }>()
const emit = defineEmits<{ select: [id: string]; side: [side: ClinicalSide] }>()
const t = (key: StringKey) => translate(props.locale, key)
const query = ref('')
const regions = computed(() => props.catalog.anatomy.filter(node => node.kind === 'region' && node.status === 'active'))
const region = computed(() => regionOf(props.nodes, props.selectedId))
const children = (id: string) => props.catalog.anatomy.filter(node => node.parent === id && node.kind !== 'tooth')
const structures = computed(() => children(region.value).flatMap(node => [node, ...children(node.id)]))
const selectedNode = computed(() => props.nodes.get(props.selectedId))
const sides = computed(() => sideChoices(selectedNode.value))
const results = computed(() => {
  const needle = query.value.trim().toLocaleLowerCase()
  if (needle.length < 2) return []
  return props.catalog.anatomy.filter(node => Object.values(node.label).some(label => label.toLocaleLowerCase().includes(needle))).slice(0, 12)
})
const scope = computed(() => props.catalog.imaging_scope[region.value])
const label = (id: string) => nodeLabel(props.nodes, id, props.locale)
function choose(id: string) { query.value = ''; emit('select', id) }
</script>

<template>
  <section class="ct-panel ct-navigator" :aria-label="t('choose_area')">
    <div class="ct-panel-head"><h2>{{ t('choose_area') }}</h2></div>
    <label class="ct-search"><span class="sr-only">{{ t('search') }}</span><input v-model="query" type="search" :placeholder="t('search')" :disabled="locked" autocomplete="off" /></label>
    <ul v-if="results.length" class="ct-search-results" role="listbox" :aria-label="t('search')">
      <li v-for="node in results" :key="node.id"><button type="button" role="option" :aria-selected="node.id === selectedId" @click="choose(node.id)">{{ label(node.id) }}<small v-if="node.parent">{{ label(regionOf(nodes, node.id)) }}</small></button></li>
    </ul>
    <div class="ct-chip-row" role="group" :aria-label="t('choose_area')">
      <button v-for="node in regions" :key="node.id" type="button" class="ct-chip" :aria-pressed="region === node.id" :disabled="locked" @click="choose(node.id)">{{ label(node.id) }}</button>
    </div>
    <div v-if="structures.length" class="ct-structures">
      <h3>{{ t('structures') }} · {{ label(region) }}</h3>
      <div class="ct-chip-row">
        <button v-for="node in structures" :key="node.id" type="button" class="ct-chip small" :class="{ nested: node.parent !== region }" :aria-pressed="node.id === selectedId"
          :disabled="locked" @click="choose(node.id)">{{ label(node.id) }}</button>
      </div>
    </div>
    <div v-if="region === 'body.mouth'" class="ct-teeth" role="group" :aria-label="t('teeth_chart')">
      <h3>{{ t('teeth_chart') }}</h3>
      <div v-for="(row, index) in chartRows" :key="index" class="ct-teeth-row" dir="ltr">
        <span class="ct-teeth-label">{{ index === 0 ? t('upper') : t('lower') }}</span>
        <button v-for="fdi in row" :key="fdi" type="button" class="ct-tooth" :class="{ selected: selectedId === `tooth.fdi.${fdi}` }" :aria-pressed="selectedId === `tooth.fdi.${fdi}`"
          :aria-label="label(`tooth.fdi.${fdi}`)" :title="label(`tooth.fdi.${fdi}`)" :disabled="locked" @click="choose(`tooth.fdi.${fdi}`)">{{ fdi }}</button>
      </div>
      <p class="ct-note">{{ t('side_note') }}</p>
    </div>
    <fieldset v-if="sides.length > 1" class="ct-side" :disabled="locked">
      <legend>{{ t('side') }}</legend>
      <label v-for="value in sides" :key="value" class="ct-radio"><input type="radio" name="clinical-side" :value="value" :checked="side === value" @change="emit('side', value)" />{{ t(`side_${value}` as StringKey) }}</label>
      <p class="ct-note">{{ t('side_note') }}</p>
    </fieldset>
    <p v-else-if="selectedNode?.fixed_side" class="ct-note">{{ t('side') }}: {{ t(`side_${selectedNode.fixed_side}` as StringKey) }}</p>
    <details v-if="scope" class="ct-scope">
      <summary>{{ t('photo_scope') }}</summary>
      <p><strong>{{ t('photo_can') }}:</strong> {{ scope.photo_can_show[locale] }}</p>
      <p><strong>{{ t('photo_cannot') }}:</strong> {{ scope.needs_examination[locale] }}</p>
    </details>
  </section>
</template>
