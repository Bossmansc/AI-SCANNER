import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

/**
 * Vite Configuration
 * 
 * This configuration is optimized for:
 * 1. Containerized environments (Docker, Cloud IDEs) via host: '0.0.0.0'
 * 2. React development with Fast Refresh
 * 3. Path aliases (@ -> src)
 * 4. Production build optimizations
 */
export default defineConfig({
  plugins: [
    react()
  ],
  
  resolve: {
    alias: {
      // Allows imports like "import Component from '@/components/Component'"
      "@": path.resolve(__dirname, "./src"),
    },
  },

  server: {
    // Bind to all network interfaces to allow access from outside the container/VM
    host: '0.0.0.0', 
    port: 5173,
    // If port 5173 is in use, fail rather than trying the next available port
    // This ensures deterministic port binding for proxy configurations
    strictPort: true,
    cors: true,
    // Watcher options to ensure file changes are detected in virtualized filesystems
    watch: {
      usePolling: true,
      interval: 100,
    },
    // HMR (Hot Module Replacement) configuration
    hmr: {
      // Ensure the client connects to the correct port, useful behind reverse proxies
      clientPort: 5173, 
    }
  },

  preview: {
    // Preview server configuration (npm run preview)
    host: '0.0.0.0',
    port: 4173,
    strictPort: true,
  },

  build: {
    // Output directory for production build
    outDir: 'dist',
    // Generate sourcemaps for better debugging in production
    sourcemap: true,
    // Minification options
    minify: 'esbuild',
    // Rollup options for chunk splitting
    rollupOptions: {
      output: {
        manualChunks: (id) => {
          // Split vendor modules into separate chunks for better caching
          if (id.includes('node_modules')) {
            if (id.includes('react') || id.includes('react-dom')) {
              return 'vendor-react';
            }
            // Group other large libraries if necessary
            return 'vendor'; 
          }
        },
      },
    },
  },

  // Optimize dependencies that might be slow to compile
  optimizeDeps: {
    include: ['react', 'react-dom'],
  },
});
