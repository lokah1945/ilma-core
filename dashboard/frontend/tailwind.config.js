/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: '#3b82f6',
        success: '#22c55e',
        warning: '#eab308',
        danger: '#ef4444',
      }
    },
  },
  plugins: [],
}