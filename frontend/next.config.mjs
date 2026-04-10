/** @type {import('next').NextConfig} */
const isMobile = process.env.NEXT_BUILD_MODE === "mobile";

const nextConfig = {
  ...(isMobile && {
    output: "export",
    images: {
      unoptimized: true,
    },
  }),
};

export default nextConfig;
