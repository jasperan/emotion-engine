/** @type {import('tailwindcss').Config} */
export default {
	content: ['./src/**/*.{html,js,svelte,ts}'],
	theme: {
		extend: {
			fontFamily: {
				'display': ['Playfair Display', 'serif'],
				'mono': ['JetBrains Mono', 'monospace'],
				'sans': ['DM Sans', 'system-ui', 'sans-serif']
			},
			colors: {
				'storm': {
					50: '#f0f5ff',
					100: '#e0eaff',
					200: '#c7d7fe',
					300: '#a4bcfc',
					400: '#7a95f8',
					500: '#5a6df2',
					600: '#4349e6',
					700: '#3838d2',
					800: '#2f30a9',
					900: '#2c2e85',
					950: '#1a1a4e'
				},
				'flood': {
					50: '#effbfc',
					100: '#d6f4f7',
					200: '#b2e8ef',
					300: '#7dd6e3',
					400: '#40bace',
					500: '#249eb3',
					600: '#218097',
					700: '#21677b',
					800: '#235565',
					900: '#214856',
					950: '#102e3a'
				}
			},
			animation: {
				'pulse-slow': 'pulse 4s cubic-bezier(0.4, 0, 0.6, 1) infinite',
				'float': 'float 6s ease-in-out infinite'
			},
			keyframes: {
				float: {
					'0%, 100%': { transform: 'translateY(0px)' },
					'50%': { transform: 'translateY(-10px)' }
				}
			}
		}
	},
	plugins: []
};

