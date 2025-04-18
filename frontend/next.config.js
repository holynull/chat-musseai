/** @type {import('next').NextConfig} */
const nextConfig = {
	images: {
		remotePatterns: [{
			protocol: 'https',
			hostname: 'images.bridgers.xyz',
			port: '',
			pathname: '/**',
		}, {
			protocol: 'https',
			hostname: 'raw.githubusercontent.com',
			port: '',
			pathname: '/**',
		},],
	},
};

module.exports = nextConfig;
