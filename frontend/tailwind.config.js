/** @type {import('tailwindcss').Config} */
export default {
	content: ['./src/**/*.{html,js,svelte,ts}'],
	theme: {
		extend: {
			fontFamily: {
				sans: ['Inter', 'system-ui', 'sans-serif'],
				mono: ['JetBrains Mono', 'monospace']
			},
			colors: {
				storm: {
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
				flood: {
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
				},
				// Google AI Studio inspired palette
				background: '#131314', // Very dark grey/almost black
				surface: '#1E1F20',    // Slightly lighter for cards/sidebars
				surface_alt: '#28292A', // Hover states
				primary: '#A8C7FA',    // Light blue accent
				on_primary: '#042D5F', // Text on primary
				on_background: '#E3E3E3', // High emphasis text
				on_surface: '#C4C7C5',    // Medium emphasis text
				outline: '#444746',       // Borders
				accent: {
					blue: '#A8C7FA',
					purple: '#D0BCFF',
					teal: '#73F7E9'
				}
			},
			backgroundImage: {
				'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
				'subtle-glow': 'conic-gradient(from 180deg at 50% 50%, #1e1f2000 0deg, #a8c7fa10 180deg, #1e1f2000 360deg)',
			}
		}
	},
	plugins: []
};


