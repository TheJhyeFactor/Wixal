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
| Product imagery | Generated wide app mockup | Intentional deviation: authentic Wixal screenshots retain their original aspect ratio in the hero; product cards crop real screenshots. Companion uses a labelled code-native explanatory illustration because a released companion screenshot is unavailable |
| Closing | Three open columns, large download statement, sparse three-column footer | Same copy and structure; added persistent light/dark appearance controls to match the reference's functionality |
| Controls | Download and screenshot selector | SVG arrow icons, real release assets, accessible tabs supporting ArrowLeft/Right, Home/End, and Escape dismissal of navigation |

The source-grounded product page expands the four catalogue areas using the same design system. Additional Models, Resources, and Download pages are functional continuations of this system. Copy for these pages follows the published README, release assets, connections guide, user guide, and architecture documentation.

Hero allowed-copy check: navigation and headline/subtitle/CTA text retain the concept wording. The download icon, original Wixal screenshot contents, mobile menu, and appearance controls are intentional additions. No invented social proof, prices, certifications, customer logos, or product capabilities were added.

Temporary QA screenshots are saved outside website source in the main workspace's ignored artifacts/website directory. Browser checks use the Codex in-app browser, including a 1505×1045 native concept-size viewport and mobile breakpoint checks. Screenshots are inspected alongside the concepts with view_image. Production deployment verification is recorded in the task handoff.
