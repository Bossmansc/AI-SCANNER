import { defineConfig, loadEnv, type UserConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath, URL } from 'node:url';

/**
 * Vite Configuration
 * 
 * This configuration sets up the development server, build process, and API proxying.
 * It uses the 'loadEnv' utility to access environment variables prefixed with VITE_
 * (or others if explicitly requested) to configure the proxy target dynamically.
 */
export default defineConfig(({ mode }: { mode: string }): UserConfig => {
  // Load env file based on `mode` in the current working directory.
  // The third parameter '' allows loading all env vars, not just those with VITE_ prefix,
  // which is useful if you need to access system-level variables like PORT.
  const env = loadEnv(mode, process.cwd(), '');

  // Define the backend target URL. 
  // Priority: Environment Variable -> Localhost Fallback
  const API_TARGET = env.VITE_API_TARGET || 'http://localhost:8000';

  console.log(`[Vite] Running in ${mode} mode`);
  console.log(`[Vite] Proxying API requests to: ${API_TARGET}`);

  return {
    plugins: [
      react(),
      // Add other plugins here (e.g., vite-plugin-svgr, vite-tsconfig-paths)
    ],

    resolve: {
      alias: {
        // Maps '@' to the './src' directory for cleaner imports
        '@': fileURLToPath(new URL('./src', import.meta.url)),
      },
    },

    server: {
      // Listen on all local IPs (0.0.0.0) to allow access from network devices
      host: true, 
      port: parseInt(env.PORT || '5173'),
      strictPort: false, // If port is taken, try the next one
      open: false, // Do not open browser automatically on start
      
      // API Proxy Configuration
      proxy: {
        '/api': {
          target: API_TARGET,
          changeOrigin: true,
          secure: false, // Allow self-signed certificates in dev
          
          // Rewrite the path: remove '/api' prefix before forwarding to backend
          // Example: /api/users -> http://localhost:8000/users
          // If your backend expects /api/users, comment out the rewrite function.
          rewrite: (path) => path.replace(/^\/api/, ''),

          configure: (proxy, _options) => {
            proxy.on('error', (err, _req, _res) => {
              console.log('[Proxy Error]:', err);
            });
            proxy.on('proxyReq', (proxyReq, req, _res) => {
              // Optional: Log outgoing requests for debugging
              // console.log('[Proxy Request]:', req.method, req.url, '->', API_TARGET + proxyReq.path);
            });
            proxy.on('proxyRes', (proxyRes, req, _res) => {
              // Optional: Log responses
              // console.log('[Proxy Response]:', proxyRes.statusCode, req.url);
            });
          },
        },
        
        // WebSocket Proxying (if your backend uses Socket.io or raw WS)
        '/socket.io': {
          target: API_TARGET,
          ws: true,
          changeOrigin: true,
          secure: false,
        },
      },
    },

    build: {
      outDir: 'dist',
      assetsDir: 'assets',
      // Generate sourcemaps for better debugging in production (disable if security concern)
      sourcemap: mode === 'development', 
      // Minification strategy
      minify: 'esbuild',
      // Raise the warning limit for chunk size (default is 500kb)
      chunkSizeWarningLimit: 1000,
      
      rollupOptions: {
        output: {
          // Manual chunk splitting to optimize cache hits
          manualChunks: (id) => {
            if (id.includes('node_modules')) {
              if (id.includes('react') || id.includes('react-dom')) {
                return 'vendor-react';
              }
              if (id.includes('lodash') || id.includes('underscore')) {
                return 'vendor-utils';
              }
              // Default vendor chunk for other node_modules
              return 'vendor';
            }
          },
        },
      },
    },

    // Preview server config (used when running `vite preview`)
    preview: {
      port: 4173,
      host: true,
      proxy: {
        '/api': {
          target: API_TARGET,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, ''),
        },
      },
    },

    // Optimization settings
    optimizeDeps: {
      include: ['react', 'react-dom'],
    },
  };
});
