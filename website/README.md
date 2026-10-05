# Wixal website

The Wixal marketing website. Six static pages: Home, Products, Tools, Models, Resources, and Download. Shared navigation, footer, keyboard-accessible screenshot tabs, mobile navigation, and persistent light/dark appearance controls.

## Develop

Requires Node 22 or newer. No additional website dependencies or install step.

```sh
cd website
npm run dev
```

Open http://127.0.0.1:4173. The dev command builds once; after editing, run `npm run build` and reload the browser.

## Build and check

```sh
npm run build
npm run check
```

For the GitHub Pages project URL:

```sh
BASE_PATH=/Wixal/ npm run build
BASE_PATH=/Wixal/ npm run check
BASE_PATH=/Wixal/ npm run dev
```

The output is `dist/`. Deploy only that folder. `BASE_PATH` sets a subdirectory prefix. `SITE_ORIGIN` sets the origin for canonical URLs, sharing metadata, and the sitemap. Change both for a custom domain deployment.

## Version control and deployment

Source lives on `codex/wixal-website`. The website workflow checks pull requests and publishes pushes on `main` and `codex/wixal-website` to GitHub Pages. The initial site publishes from the website branch so the existing app work on `main` can remain independent. Once the website is merged, remove the feature branch from the workflow's publishing branches.

GitHub Pages must use GitHub Actions as its build source. The published URL is https://thejhyefactor.github.io/Wixal/.

## Content and assets

`scripts/build.mjs` contains the shared templates and page content. `src/styles.css` defines the responsive design system; `src/site.js` handles navigation, screenshot tabs, and appearance. Wixal 0.7.0 workspace, model manager, tool kit and performance captures are saved as WebP. Files, memory, terminal, connections, explicit tool selection, command tools, web tool cards and MCP setup previews are captured from 0.7.0, and the existing folded W mark is used in the header and favicon.

The Cursor homepage and product page informed the neutral palette, quiet navigation, typography, whitespace, product previews, and download buttons. Wixal uses its own content and assets. No Cursor fonts, logo, screenshots, customer endorsements, or product claims are shipped.

Download links target the verified v0.7.0 release. Update the release version and copy in `scripts/build.mjs` when shipping a new release. Provider features follow the current published Wixal docs. The companion illustration is labelled as an illustration, not a screenshot. All site pages and download links work without JavaScript. Mobile navigation, screenshot switching, and appearance controls use JavaScript.

Design concepts in `design/` were created with the built-in image generation tool. They are development references and are not part of the published site. Their brief was to retain the Cursor product page's #f7f7f4 / #26251e palette, understated regular grotesk type, open spacing, existing Wixal folded W branding, four source-grounded product areas, and the download/footer continuation. Actual Wixal screenshots intentionally replace generated app mockups. See `design/verification.md` for comparison notes.

## Refresh the screenshots

With the desktop app dependencies installed, run:

```sh
node website/scripts/capture-features.cjs /absolute/path/to/Wixal
```

The feature capture script opens the actual desktop app using temporary project and app data, previews real files and tool controls, saves a project note, and executes the sample project's test in its terminal. It uses external-runtime mode and requires an already-running local Ollama connection; it does not download, import or run a model. It also captures the empty MCP configuration dialog, not a connected service. It removes only this temporary fixture after capture. Capture from the release version used by the site. No model response is fabricated and no provider credential is configured. The example terminal output is an actual passing test run.

The build reads intrinsic WebP dimensions directly and uses them in each image's HTML. Preview frames reserve the same proportions before lazy loading, keeping section links stable. The check validates image attributes against their source dimensions. Header and footer theme controls share a saved preference, which is applied before the stylesheet loads to avoid a flash of the opposite theme.

Styles, scripts, and screenshots use content-derived asset versions so browsers fetch updated files after a deployment.

The 0.7.0 update uses the actual release app captures in `docs/screenshots`, including reported usage and a completed real benchmark. The local engine, tool defaults, model manager and macOS minimum match this release.

The Tools page explains explicit tool selection, reviewed file edits, command sessions, rendered web inspection, search, JSON APIs and external MCP setup. Product memory includes notes, prior-chat search and inspectable summaries. The dark appearance uses the live Cursor reference's near-black background, raised surfaces, off-white text, subtle borders and restrained orange accents; it also styles the navigation, footer, screenshot frames, gallery, buttons and enlarged viewer. Light appearance retains the original neutral palette.
