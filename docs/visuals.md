# Wixal logo and motion

The folded W is the first letter of Wixal. The remaining letters sit beside it as one continuous name. Warm white and sakura pink sit against charcoal, matching the app. The symbol is also the Mac app icon.

Open [the visual preview](brand.html) locally to inspect the logo variants, small icon sizes, and product recordings. Its pause button switches every GIF to a still image, and system reduced motion settings pause motion automatically.

## Logo files

| Asset | Vector | Raster |
| --- | --- | --- |
| Primary logo for dark backgrounds | [wixal.svg](../assets/logo/wixal.svg) | [wixal.png](../assets/logo/wixal.png) |
| Logo for light backgrounds | [wixal-dark.svg](../assets/logo/wixal-dark.svg) | [wixal-dark.png](../assets/logo/wixal-dark.png) |
| Single colour logo | [wixal-mono.svg](../assets/logo/wixal-mono.svg) | [wixal-mono.png](../assets/logo/wixal-mono.png) |
| Symbol | [symbol.svg](../assets/logo/symbol.svg) | [symbol.png](../assets/logo/symbol.png) |
| Wordmark | [wordmark.svg](../assets/logo/wordmark.svg) | SVG |
| Mac app icon | [app-icon.svg](../assets/app-icon.svg) | [icon.png](../assets/icon.png), [Wixal.icns](../assets/Wixal.icns) |
| Logo reveal | [logo-reveal.svg](../assets/motion/logo-reveal.svg) | [logo-reveal.gif](../assets/motion/logo-reveal.gif) |

The symbol and lettering are drawn as vector paths. They don't depend on a font installation. The PNG logo exports have transparent backgrounds. Keep the proportions intact and leave clear space around the logo; use the symbol alone where the full name would be too small. Use the light background version on white or pale surfaces, and the primary version on charcoal.

## Page graphics and recordings

| Graphic | Files |
| --- | --- |
| GitHub header | [Animated GIF](../assets/motion/github-hero.gif), [static SVG](../assets/repo-banner.svg), [static PNG](../assets/repo-banner.png) |
| Social preview | [SVG](../assets/social-card.svg), [PNG](../assets/social-card.png) |
| Full workspace tour | [GIF](media/workspace-tour.gif), [workspace still](screenshots/workspace.png) |
| Model picker | [GIF](media/choose-model.gif), [model still](screenshots/models.png) |
| Project files | [GIF](media/project-files.gif), [file still](screenshots/files.png) |
| Terminal | [GIF](media/terminal.gif), [terminal still](screenshots/terminal.png) |

The recordings are made from real app interactions with a temporary project. The model clip opens the picker, filters the installed library, and selects a model. The file clip previews real fixture files and adds code to the prompt. The terminal clip runs `node hello.js` in the actual PTY and waits for its output. Captions are added after capture. None of these clips simulate model inference or approval results.

The header and logo GIFs reveal the letters from the W, hold the complete name, then repeat. The animated SVG plays once and settles. The four product GIFs also loop. The GIF files themselves do not respond to reduced motion settings, so every recording has a still image link beside it. The local preview provides a global pause control. The animated SVG and app transitions respect `prefers-reduced-motion`.

The social card is exported for use in GitHub's separate repository social preview setting. Committing that image does not apply the setting automatically.

## Rebuild

```sh
npm run assets
npm run media
npm run assets
npm run motion
```

Build the logo and icons, record the current app, rebuild the header with the fresh workspace screenshot, then export the header and logo animations. `assets` uses macOS `iconutil` for the ICNS. `media` needs Ollama and the Qwen model used by its search demonstration.

Edit [graphics.cjs](../scripts/graphics.cjs) for the vector identity and layouts, [motion.cjs](../scripts/motion.cjs) for GIF timing, or [capture-media.cjs](../scripts/capture-media.cjs) for app recordings. The [interface icon set](../assets/icons) uses consistent 24 pixel SVGs.

## Illustration provenance

The previously created shrine artwork remains an accent in the app. It was generated with the built-in image generation tool and is illustrative artwork, not a photograph of a real location. Its [source image](../assets/artwork/night-shrine.png) and [generation prompt](artwork-prompt.txt) are preserved. The new logo, wordmark, layouts, and motion are defined directly in repository code.
