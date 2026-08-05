import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  // Required for production Docker deployment (copies standalone output)
  output: 'standalone',
};

export default nextConfig;
