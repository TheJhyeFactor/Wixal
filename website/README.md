# Wixal website

The Wixal marketing website. Five static pages: Home, Products, Models, Resources, and Download. Shared navigation, footer, keyboard-accessible screenshot tabs, mobile navigation, and persistent light/dark appearance controls.

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

`scripts/build.mjs` contains the shared templates and page content. `src/styles.css` defines the responsive design system; `src/site.js` handles navigation, screenshot tabs, and appearance. Existing Wixal screenshots were converted to WebP, and the existing folded W mark is used in the header and favicon.

The Cursor homepage and product page informed the neutral palette, quiet navigation, typography, whitespace, product previews, and download buttons. Wixal uses its own content and assets. No Cursor fonts, logo, screenshots, customer endorsements, or product claims are shipped.

Download links target the verified v0.5.1 release. Update the release version and copy in `scripts/build.mjs` when shipping a new release. Provider features follow the current published Wixal docs. The companion illustration is labelled as an illustration, not a screenshot. All site pages and download links work without JavaScript. Mobile navigation, screenshot switching, and appearance controls use JavaScript.

Design concepts in `design/` were created with the built-in image generation tool. They are development references and are not part of the published site. Their brief was to retain the Cursor product page's #f7f7f4 / #26251e palette, understated regular grotesk type, open spacing, existing Wixal folded W branding, four source-grounded product areas, and the download/footer continuation. Actual Wixal screenshots intentionally replace generated app mockups. See `design/verification.md` for comparison notes.
