import { defineConfig } from 'steiger'
import fsd from '@feature-sliced/steiger-plugin'

export default defineConfig([
  ...fsd.configs.recommended,
  {
    // Долг из /arch detect. Правило в warn, пока его нарушения не исправлены
    rules: {},
  },
])
