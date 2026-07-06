import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'ujuiceqnvkwcizliwvcf.supabase.co',
      },
    ],
  },
};

export default nextConfig;
