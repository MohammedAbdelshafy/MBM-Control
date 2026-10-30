import { defineConfig } from 'vitest/config';

/**
 * Isolated LeadEngine unit-test config.
 *
 * The monorepo root Vite config belongs to the web application and loads
 * frontend-only plugins. The LeadEngine package is a Node/Vitest workspace.
 */
export default defineConfig({
  test: {
    environment: 'node',
    include: ['tests/**/*.test.ts'],
    exclude: ['node_modules', 'dist'],
    clearMocks: true,
    restoreMocks: true,
  },
});
