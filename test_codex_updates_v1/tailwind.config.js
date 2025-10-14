/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'nfl-primary': '#013369',
        'nfl-secondary': '#D50A0A',
        'fantasy-green': '#00FF00',
        'sleeper-gold': '#FFD700',
      }
    },
  },
  plugins: [],
}