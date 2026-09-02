<template>
  <div class="card">
    <h3>筛选</h3>
    <div class="row">
      <label>起始
        <input type="date" v-model="since" />
      </label>
      <label>结束
        <input type="date" v-model="until" />
      </label>
      <button @click="$emit('apply', { since, until })">应用</button>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
defineEmits(['apply'])
const since = ref('')
const until = ref('')
</script>
