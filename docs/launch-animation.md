# Wixal wordmark startup

The splash plays one refined version of Wixal's original wordmark animation. Its paths, circles, ellipse, proportions and rounded lettering come directly from `assets/logo/wordmark.svg`; the name-window and name-slide reveal follows `assets/motion/logo-reveal.svg`.

The full wordmark sits on the selected app theme's background. A subtle drop shadow follows the actual letters. Ink and the folded accent use the theme's text and accent colours. The current app version appears in small text beneath the name.

The reveal lasts 2.1 seconds: a slight settling movement, the original name reveal, the folded accent resolving, the version appearing, a short hold, and a gentle exit into the workspace. There is one sequence for every launch. The paper shapes, layered sheets, decorative effects, random selection and probabilities have been removed.

Escape skips the intro and stops the sound. Launch-animation, launch-sound and reduced-motion settings retain their behaviour; the Mac's reduced-motion preference also applies. Startup has a three-second fallback while preferences load or rendering fails, and does not wait for the model/runtime connection.

Validation: `node --test test/launch-motion.test.cjs`, `npm run check`, and `npm run test:launch`. Tests compare the splash geometry with the original asset and exercise partial/full reveal widths, theme colours, drop shadow, transparent surrounding surface, dynamic version, audio, Escape, automatic dismissal, saved settings and reduced motion. Set `WIXAL_APP_PATH` to verify a packaged or installed executable with isolated temporary data.
