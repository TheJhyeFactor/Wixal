# Logo & motion

The Wixal logo uses the folded W as the first letter of the name. In the reveal animation, the W stays in place while “ixal” appears beside it.

## Logo files

| Asset | File |
| :--- | :--- |
| Animated logo used in the README | [logo-reveal.gif](../assets/motion/logo-reveal.gif) |
| Animated vector version | [logo-reveal.svg](../assets/motion/logo-reveal.svg) |
| Still version of the README header | [logo-reveal-still.png](../assets/motion/logo-reveal-still.png) |
| Logo for dark backgrounds | [SVG](../assets/logo/wixal.svg) · [PNG](../assets/logo/wixal.png) |
| Logo for light backgrounds | [SVG](../assets/logo/wixal-dark.svg) · [PNG](../assets/logo/wixal-dark.png) |
| W symbol | [SVG](../assets/logo/symbol.svg) · [PNG](../assets/logo/symbol.png) |

The README uses the existing GIF for playback on GitHub. A picture source supplies the still frame when the browser requests reduced motion. The animated SVG also supports reduced motion.

## Feature artwork

[features-0.6.svg](../assets/features-0.6.svg) is the static release feature overview used in the README. It uses the same dark surfaces and muted pink accents as the app. Text describes shipped behaviours; app screenshots and the tour come from real UI captures.

## App screenshots and tour

The [screenshots](screenshots) and [app tour](media/workspace-tour.gif) show Wixal 0.6.0 running with a disposable demo project. The tour covers model selection, project files, tool controls, external MCP setup, notes, and the terminal. Captions are added after recording; the tour does not stage model replies or approval results.

To record updated screenshots and a tour:

```sh
npm run media
```

The capture script needs Ollama running with a model installed. It uses temporary app data and leaves your saved projects and conversations alone.

Keep screenshots current when the interface changes. Check them for private paths, credentials, and personal conversations before publishing.

[Back to Wixal](../README.md)
