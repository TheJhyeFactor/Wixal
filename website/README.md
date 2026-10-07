# Wixal website

A restrained static website that follows the native workspace’s Paper appearance: warm neutral surfaces, quiet dividers, the monospace Wixal wordmark and one actual workspace screenshot. Dark appearance is available in the footer.

Eight pages cover Home, Workspace, Tools, Models, Guides, Download, Privacy and Download stats. Existing routes and product section anchors remain available. The homepage screenshot is labelled **native local development preview**; downloads explicitly identify the released **Electron app**. Update the version in `scripts/build.mjs` only after checking the actual release assets.

## Develop and check

Requires Node 22 or newer. No website dependencies or install step.

```sh
npm run dev
```

Open http://127.0.0.1:4173. The server does not watch sources; rebuild and reload after changes.

```sh
BASE_PATH=/Wixal/ npm run build
BASE_PATH=/Wixal/ npm run check
BASE_PATH=/Wixal/ npm run dev
```

Deploy only `dist/`. `BASE_PATH` sets the project URL prefix, and `SITE_ORIGIN` controls canonical URLs and the sitemap. Checks cover JavaScript syntax, local page/asset/fragment links, opt-in analytics and aggregate report validation.

## Presentation

`scripts/build.mjs` owns templates and copy. `src/styles.css` defines the responsive layout; `src/site.js` handles persistent appearance and the keyboard-accessible image dialog. Escape closes the dialog and focus returns to its trigger. Reduced-motion preferences disable entrance and hover animation.

`public/assets/native-workspace.png` is an actual installed native app capture from a disposable project named Wixal, with no fabricated messages or results. It is the only content image displayed by the site. Older captures remain as source assets but are not displayed. `social-card.svg` is the source for the matching typographic sharing card, rendered to `social-card.png`. Styles, scripts and displayed assets have content-derived cache versions.

The README on GitHub is text focused: current downloads, a capability table, getting-started steps, the native preview distinction and guide links.

## Deployment

The GitHub Pages workflow builds and checks website changes. The published URL is https://thejhyefactor.github.io/Wixal/. Pages uses GitHub Actions rather than a committed `dist/` directory.

## Privacy and public counts

See [metrics setup](../docs/download-metrics.md). Google Analytics loads only after explicit opt-in; decline, revocation and cross-tab changes remain supported. The desktop app is unaffected. Counters live on the stats page, keeping the homepage quiet.

GitHub counts DMG/ZIP downloads, including repeat downloads. These are separate from opted-in website visitors and do not establish installations or active app users.
