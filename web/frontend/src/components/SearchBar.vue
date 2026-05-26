<template>
  <div class="search-bar">
    <input
      v-model="keyword"
      :placeholder="placeholder"
      @keyup.enter="emit('search', keyword)"
    />
    <button class="btn" @click="emit('search', keyword)">搜索</button>
  </div>
</template>

<script setup>
import { ref } from 'vue'

defineProps({
  placeholder: { type: String, default: '搜索非遗项目...' },
})

const emit = defineEmits(['search'])
const keyword = ref('')
</script>

<style scoped>
.search-bar {
  display: flex;
  gap: 8px;
}

.search-bar input {
  flex: 1;
  padding: 12px 16px;
  font-size: 15px;
  border: 2px solid var(--border);
  border-radius: var(--radius);
}

.search-bar input:focus {
  border-color: var(--primary);
}

.search-bar .btn {
  padding: 12px 28px;
  font-size: 15px;
  white-space: nowrap;
}
</style>
