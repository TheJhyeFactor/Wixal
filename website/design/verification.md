# Design direction and browser verification

Reference: https://cursor.com/product and https://cursor.com, inspected live on 6 October 2026 (Australia/Sydney).

The product page was observed with background rgb(247,247,244), regular-weight grotesk headings, charcoal foreground, muted grey supporting type, a quiet header, pill download buttons, understated neutral media panels, and product-focused section layouts. The implementation uses #f7f7f4, #26251e, #787870, #efefea, #deddd3, and #a44622, with Arial/Helvetica instead of Cursor's proprietary font.

## Concept comparison

Built-in Image Gen created three coordinated section references, inspected with view_image before coding: home-hero.png, products.png, and closing.png. The production website uses authentic Wixal media rather than generated app imagery.

| Comparison | Concept evidence | Implementation decision |
| --- | --- | --- |
| Header | Folded W, Wixal, Models, Products, Resources, GitHub, Download | Existing W vector and the same navigation order, centred desktop links, a real products disclosure, and mobile menu |
| Hero copy | A place for your next idea. / AI, project files, and a terminal. / Together on your Mac. | Exact text retained; real download link and product page action |
| Palette | Off-white background, charcoal heading/button, grey secondary text, taupe media panel | Exact source-derived colour tokens; no gradient, glow, or coloured marketing illustration |
| Typography | Regular grotesk headings and body, deliberate scale hierarchy | 54px desktop hero, 44px supporting copy, 40px section headings; responsive reductions |
| Product catalogue | Two columns, four quiet panels, orange text links, large dark product media | Same order, copy, two-column layout, surfaces, and link treatment; one-column mobile layout |
| Product imagery | Generated wide app mockup | Intentional deviation: authentic Wixal screenshots retain their original aspect ratio in the hero; product cards originally cropped real screenshots; the follow-up below keeps complete screenshots visible. Companion uses a labelled code-native explanatory illustration because a released companion screenshot is unavailable |
| Closing | Three open columns, large download statement, sparse three-column footer | Same copy and structure; added persistent light/dark appearance controls to match the reference's functionality |
| Controls | Download and screenshot selector | SVG arrow icons, real release assets, accessible tabs supporting ArrowLeft/Right, Home/End, and Escape dismissal of navigation |

The source-grounded product page expands the four catalogue areas using the same design system. Additional Models, Resources, and Download pages are functional continuations of this system. Copy for these pages follows the published README, release assets, connections guide, user guide, and architecture documentation.

Hero allowed-copy check: navigation and headline/subtitle/CTA text retain the concept wording. The download icon, original Wixal screenshot contents, mobile menu, and appearance controls are intentional additions. No invented social proof, prices, certifications, customer logos, or product capabilities were added.

Temporary QA screenshots are saved outside website source in the main workspace's ignored artifacts/website directory. Browser checks use the Codex in-app browser, including a 1505×1045 native concept-size viewport and mobile breakpoint checks. Screenshots are inspected alongside the concepts with view_image. Production deployment verification is recorded in the task handoff.

## Initial publication verification (superseded where noted below)

- GitHub Actions completed both the app Check workflow and website build/deploy workflow successfully for implementation commit db67466f25e9cf22c258765a846905373dc4906a.
- All five live page URLs returned HTTP 200 and were inspected in the in-app browser. The deployed content, original screenshots, and /Wixal/ page and asset paths were verified.
- At 1505×1045, the live hero, catalogue, and closing/footer screenshots were inspected with view_image alongside all three original concepts. Copy, layout, colour, typography, media, spacing, and footer structure were compared. The source-grounded asset differences above remain intentional; the first pass did not detect the fixed-height image defect in the later product sections. The user reported it and the follow-up below corrects it.
- At 390×844, all five pages were checked for horizontal page overflow. None was found. The product subnavigation uses a contained horizontal scroll rail on mobile.
- The mobile menu was corrected to close after a section selection. Selecting Terminal & tools updates the URL fragment and closes the menu.
- The screenshot gallery was exercised with mouse and keyboard. ArrowRight switches Files to Terminal; Home restores Workspace; the visible screenshots load successfully.
- Escape dismisses the desktop Products disclosure. Dark appearance switches the background to rgb(20,18,11), survives reload, and can be restored to Light.
- No browser error or warning was recorded during the published desktop pass. The download buttons target the verified release DMG and ZIP assets.
- npm run build, npm run check, and git diff --check pass; the check resolves 180 local page, fragment, and asset links across six HTML documents, including the 404 page.

## Screenshot and theme follow-up

The reported product/#connections defect was reproduced at 1280px: a screenshot constrained to roughly 674px wide retained its HTML height of 1234px. The responsive base image rule now uses automatic height. Intrinsic dimensions are read from each WebP during the build, and feature preview buttons reserve the image ratio before lazy loading. Section spacing is outside the anchor target so deep links land on the heading.

Fresh actual Wixal 0.6.0 UI captures use a disposable sample project and app state. Focused files, model picker, memory, toolkit, terminal, and connections captures avoid the blurred background of modal screenshots. The terminal capture shows an actual passing node --test run. A reproducible capture script is included; no fabricated chat or terminal output is shown.

The home and product showcases now have four keyboard-accessible views with explanatory copy and an enlarged screenshot dialog. Product-card media uses contain instead of clipping. The site's original neutral colours and typography remain. Light/dark controls appear in the header and footer, share the saved preference across pages and tabs, and apply the saved theme before rendering. Download links use the verified v0.6.0 DMG and ZIP assets.

Follow-up local browser verification:

- At 1280x720, the Connections screenshot renders at about 525x470, matching its 1520x1360 source ratio. The files screenshot renders at about 674x440, matching 1900x1240. No fixed 1234px height remains.
- At 390x844, the Connections image renders at 310x277, matching its source proportions. All five pages have zero horizontal page overflow. The screenshot tab rail scrolls within its own container.
- A fresh product/#connections navigation places the heading at approximately y=95px, beneath the sticky header. Media has reserved space before loading.
- Light and Dark controls update both sets of pressed states. The selected theme survives page navigation and reload. Mobile navigation closes after choosing Terminal & tools.
- ArrowRight switches models to terminal and End selects memory. The viewer opens the selected screenshot; Escape closes it and restores focus to its trigger.
- A 320px narrow-width pass has no horizontal page overflow; the header download shortcut is omitted at that width, with the main download action available in the hero.
- npm run build, npm run check, and git diff --check pass. The check verifies 182 local links and validates each screenshot's width/height attributes against its WebP data.

## 0.7.0 release update

Downloads now target the published v0.7.0 assets and require macOS 14+. The model page explains the bundled Wixal Local engine, separate model library, imports, downloads, hardware filters and actual generation benchmarks. Ollama attribution remains visible. Usage and runtime guides are linked. The tool copy describes all 15 enabled built-ins and explicit @ selection.

New workspace, model-manager, toolkit and usage captures come from the actual 0.7.0 release workflow. Usage counts and Gemma 3 12B performance shown are reported by a real model run on this Mac. Unchanged files, memory, terminal and connections focus captures retain their original 0.6.0 version captions.

The updated site builds and validates 183 local links and actual WebP dimensions. Headless Chromium checks cover all five pages at widths 1280, 390 and 320: no horizontal page overflow, no broken images and correct visible image proportions. The new model page was rendered and visually inspected. Download links select v0.7.0 and the minimum version reads macOS 14+. Browser page errors were absent.

## Expanded workflows and dark appearance refresh

The site now has six pages, including a dedicated Tools page. The home catalogue covers Desktop, local models and performance, project memory and recall, terminal and command sessions, web and external tools, and the optional ChatGPT companion. Existing product fragments remain available; new memory and tool sections expand the current 0.7.0 features. Content was checked against the current release source, feature guide, local runtime guide, performance guide and cyber tools guide. The site distinguishes command sessions from the manual PTY terminal, rendered inspection from an interactive authenticated browser, and generation benchmarks from answer-quality evaluation.

Focused files, memory, terminal and connections were recaptured from the actual 0.7.0 app with disposable data. New captures show the actual @tool menu, command category, web tool cards and empty MCP setup dialog. The script runs a real node --test fixture in the manual terminal; it fabricates no model response, command-session execution, browser result or connected integration. Prior real model-manager and benchmark captures remain. All focused capture captions now correctly identify 0.7.0. The companion remains an explicitly labelled illustration.

Cursor's live dark appearance was selected and inspected on 6 October 2026. Its body background is #14120b, foreground #edecec and raised surface #1b1913. Wixal now uses those core colours with #9d9c98 secondary text, low-opacity off-white borders and an accessible #ff6c2b orange accent. The previous #302e24 media panels, pale orange links and heavy borders are replaced. Dark styling also covers navigation, gallery selection, screenshot frames, cards, secondary and primary buttons, footer, appearance controls and the enlarged viewer. Light colours remain unchanged.

Local verification for this refresh:

- Build and checks pass for six pages plus the 404 document, resolving 269 local assets, pages and fragments and validating source WebP dimensions.
- The in-app browser inspected all six pages in Light and Dark at actual widths 1280, 390 and 320. No horizontal page overflow or broken sourced images was found. The empty dialog image is excluded until its src is set. Screenshot frames retain contain sizing and intrinsic ratios.
- Desktop and mobile dark layouts were visually inspected, including the new web tool cards. A fresh tools/#web navigation places the heading at y=95px below the sticky header.
- Mobile navigation includes Tools & workflows, closes after selection, and preserves the chosen dark theme. Both header and footer pressed states match the theme, which survives navigation and reload; theme-color matches the background.
- The third home gallery tab opens the actual web tool cards. Escape dismisses the enlarged image and restores focus; End selects Project memory.
- No browser errors or warnings were recorded during the interaction pass. Download assets remain the verified uploaded v0.7.0 DMG and ZIP, requiring macOS 14+ and Apple Silicon.
