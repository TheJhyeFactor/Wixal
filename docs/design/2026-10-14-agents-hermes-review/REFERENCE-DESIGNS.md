# OpenClaw and Hermes visual reference pass

14 October 2026. Design only; no native app changes.

The user requested a new design that looks like OpenClaw and/or Hermes. This pass replaces the previous generic workspace direction with two closer visual references, retaining Wixal branding and illustrative local agent data.

## References actually inspected

- OpenClaw Agents screenshot, labelled v2026.3.13: https://content.bluehost.com/bluehost/img/bluehost/self-managed-vps/bh-openclaw-dashboard-agents-primary.png
- Current OpenClaw primary source: `ui/src/styles/base.css`, `ui/src/pages/agents/view.tsx`, and `ui/src/pages/agents/panels-overview.tsx` at https://github.com/openclaw/openclaw . Current source uses different paths from older releases and includes newer UI revisions; this is not a claim to reproduce every latest OpenClaw screen.
- OpenClaw documentation: https://docs.openclaw.ai/web/control-ui
- Official Hermes configuration screenshot: https://hermes-agent.nousresearch.com/docs/assets/images/admin-config-278bd624188f3bfb9ec51a0b51767c6e.png
- Official Hermes skills screenshot: https://hermes-agent.nousresearch.com/docs/assets/images/admin-skills-hub-28ba9342a928061ac63d5459bb6e8237.png
- Hermes documentation: https://hermes-agent.nousresearch.com/docs/user-guide/features/web-dashboard

The screenshots were viewed directly in the browser. No upstream runtime, wallpaper or branding assets were imported. Hermes's teal/cream palette, serif uppercase labels, narrow navigation and section-filter/config form structure were recreated. OpenClaw's control sidebar, profile selector, tab bar, overview metadata, rounded panel and coral selection/action accents were recreated. Its palette follows the host appearance. Wixal-specific connection labels and proposed profile fields are adaptations, not upstream or currently integrated Wixal capabilities.

## Preview verification

Browser inspection confirmed both layouts fit viewports of 320, 736 and 1024 pixels (usable content widths 288, 704 and 992), with no horizontal document overflow and no browser console errors. OpenClaw tool preset selection, file selection, saving and carousel navigation were exercised. Hermes section selection, profile selection and saving were exercised. Desktop and narrow-screen screenshots were inspected.

The preview contains local simulated interactions. No configuration, file, tool permission, model, connection or schedule is changed in Wixal. Markdown-style agent identity files in the mockup illustrate a proposed editor rather than a migration already performed.
