import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Lean, self-contained server bundle for Docker (copies only what runtime needs).
  output: "standalone",
};

export default nextConfig;
