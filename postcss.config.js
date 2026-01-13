/**
 * PostCSS Configuration
 *
 * This module configures the PostCSS transformation pipeline.
 * It is essential for processing CSS in modern web applications, specifically
 * for integrating Tailwind CSS and ensuring cross-browser compatibility
 * via Autoprefixer.
 *
 * Plugins:
 * 1. tailwindcss: Scans files for class names, generates the corresponding CSS,
 *    and writes it to a static CSS file.
 * 2. autoprefixer: Parses CSS and adds vendor prefixes to CSS rules using values
 *    from Can I Use.
 */

module.exports = {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}
