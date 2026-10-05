# Artwork and motion

Wixal uses a simple lettermark, a quiet Japanese night illustration, and small SVG icons. The application and README share the same colours and artwork.

Open [the visual preview](brand.html) locally to see the assets together, pause the animation, and play the app tour.

## Source files

| Asset | Editable source | Ready to use |
| --- | --- | --- |
| GitHub banner | [repo-banner.svg](../assets/repo-banner.svg) | [repo-banner.png](../assets/repo-banner.png) |
| Social preview | [social-card.svg](../assets/social-card.svg) | [social-card.png](../assets/social-card.png) |
| Mac app icon | [app-icon.svg](../assets/app-icon.svg) | [icon.png](../assets/icon.png), [Wixal.icns](../assets/Wixal.icns) |
| Lettermark | [mark.svg](../assets/mark.svg) | SVG |
| Workspace illustration | [night-shrine.png](../assets/artwork/night-shrine.png) | [night-shrine.webp](../assets/artwork/night-shrine.webp) |
| Workflow | [workflow.svg](../assets/workflow.svg) | SVG |
| Working indicator | [working.svg](../assets/motion/working.svg) | Animated SVG |
| App tour | [capture-media.cjs](../scripts/capture-media.cjs) | [workspace-tour.gif](media/workspace-tour.gif) |

The [icon directory](../assets/icons) contains nine SVGs for files, tools, memory, the terminal, search, new work, models, images, and review. Each uses a 24 × 24 viewBox with consistent strokes.

The banner and social card have vector text with the illustration embedded. Their PNG exports are used where SVG image support varies, including the README banner. The social card is ready for GitHub's repository social preview setting; committing the image alone does not set that repository preference.

## Rebuild or record

```sh
npm run assets
npm run media
```

`assets` rebuilds the vectors and raster exports, including the ICNS icon. It requires macOS for `iconutil`. Change the vector artwork or wording in [graphics.cjs](../scripts/graphics.cjs), then rebuild.

`media` opens the actual Electron app with a temporary project. It records the workspace, model picker, file browser, tool controls, saved memory, and interactive terminal. It needs Ollama running with at least one model installed. It does not run model inference or modify your saved workspace.

The GIF has captions added after capture and plays once. Its screenshots come from real UI interactions. No model replies or approval results are simulated.

## Motion

The welcome artwork has three small moving petals. They run for two slow cycles and then settle. Dialogs and drawers have short entrance transitions, and the working indicator animates only while a response is active.

The interface and animated SVG respect `prefers-reduced-motion`. The README keeps the GIF behind an expandable section; a static workspace screenshot is visible by default. The local visual preview lets you pause its SVG animation and opt into playing the GIF.

## Artwork provenance

The shrine illustration was generated with the built-in image generation tool for this project. It is illustrative artwork, not a photograph of a real location. The fox is drawn as part of the scene; the product logo is a separate lettermark.

The complete generation prompt is saved in [artwork-prompt.txt](artwork-prompt.txt). The SVGs, layout, captions, and motion are implemented in the repository. App screenshots and the GIF are captured from Wixal itself.
