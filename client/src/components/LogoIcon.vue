<template>
  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" :width="size" :height="size">
    <path d="M 100 40 A 65 65 0 1 0 146 59" fill="none" stroke="var(--to-accent)" stroke-width="7" stroke-linecap="round"/>
    <line x1="100" y1="40" x2="100" y2="50" stroke="var(--to-accent)" stroke-width="3.5" stroke-linecap="round"/>
    <line x1="35" y1="105" x2="45" y2="105" stroke="var(--to-accent)" stroke-width="3.5" stroke-linecap="round"/>
    <line x1="100" y1="170" x2="100" y2="160" stroke="var(--to-accent)" stroke-width="3.5" stroke-linecap="round"/>
    <line x1="54" y1="59" x2="61" y2="66" stroke="var(--to-accent)" stroke-width="3.5" stroke-linecap="round"/>
    <line x1="54" y1="151" x2="61" y2="144" stroke="var(--to-accent)" stroke-width="3.5" stroke-linecap="round"/>
    <line x1="146" y1="151" x2="139" y2="144" stroke="var(--to-accent)" stroke-width="3.5" stroke-linecap="round"/>
    <polygon points="72,82 100,60 128,82" fill="var(--to-text-primary)"/>
    <rect x="72" y="82" width="56" height="20" fill="var(--to-text-primary)" rx="2"/>
    <circle cx="90" cy="92" r="4" fill="var(--to-accent)"/>
    <circle cx="110" cy="92" r="4" fill="var(--to-accent)"/>
    <polygon points="82,102 76,148 92,148 96,102" fill="var(--to-text-primary)"/>
    <polygon points="118,102 124,148 108,148 104,102" fill="var(--to-text-primary)"/>
    <rect x="88" y="122" width="24" height="6" fill="var(--to-text-primary)"/>
    <path d="M 107 94 L 137 156 L 159 129 L 113 89 Z" fill="var(--to-accent)" opacity="0.6"/>
  </svg>
</template>

<script setup lang="ts">
withDefaults(defineProps<{ size?: number }>(), { size: 28 })
</script>
