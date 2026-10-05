# Wixal logo and motion

Download the Wixal logo, app icon, and animation files below. Use the primary logo on dark backgrounds and the dark logo on light backgrounds.

[Open the local preview](brand.html)

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

The clips show model selection, file browsing, and terminal use. Still images are available for each clip. The local preview includes a pause button and follows reduced motion settings.

Upload the social card in the repository’s social preview settings to use it on shared GitHub links.

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

The shrine illustration was generated with the built-in image generation tool. Its [source image](../assets/artwork/night-shrine.png) and [prompt](artwork-prompt.txt) are included. The logo and page graphics are SVGs defined in [graphics.cjs](../scripts/graphics.cjs).
