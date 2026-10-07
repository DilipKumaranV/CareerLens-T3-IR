import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In development, /api is proxied to the FastAPI backend so the browser
// talks to one origin. The IR logic lives only in the Python backend.
const target = process.env.CAREERLENS_API ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target,
        changeOrigin: true,
        // If the backend is not reachable, answer with a readable JSON error instead of an empty 500.
        configure: (proxy) => {
          proxy.on("error", (err, _req, res: any) => {
            if (res && typeof res.writeHead === "function" && !res.headersSent) {
              res.writeHead(502, { "Content-Type": "application/json" });
              res.end(JSON.stringify({ detail: `Vite could not reach the CareerLens API at ${target} (${err.message}). Start the backend from the backend folder: py -m uvicorn app.main:app --port 8000` }));
            }
          });
        },
      },
    },
  },
});
