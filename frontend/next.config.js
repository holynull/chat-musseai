/** @type {import('next').NextConfig} */
const nextConfig = {
	output: 'export',
	trailingSlash: true,
	images: {
		unoptimized: true,
		remotePatterns: [
			{
				protocol: 'https',
				hostname: '**',
				port: '',
				pathname: '/**',
			},
			{
				protocol: 'https',
				hostname: 'images.bridgers.xyz',
				port: '',
				pathname: '/**',
			}, {
				protocol: 'https',
				hostname: 'raw.githubusercontent.com',
				port: '',
				pathname: '/**',
			}, {
				protocol: 'https',
				hostname: 'assets.coingecko.com',
				port: '',
				pathname: '/**',
			}],
	},
};

module.exports = nextConfig;
