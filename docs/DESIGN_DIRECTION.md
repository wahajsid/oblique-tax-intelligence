# Design direction

What changed on 8 November 2026, and what a designer should take on next. The brand tokens stay as extracted from obliqueconsult.com (docs/BRAND.md).

## Done in code

- One number leads. The headline tile spans the result panel and sits at 2 to 2.6 rem; supporting tiles are smaller. Review-required results keep a dashed outline so the grey reads as deliberate.
- Hero chart instead of a table. Six horizontal bars, UAE highlighted in the green gradient, values and rates to the right. Widths animate once on load and are static when the visitor prefers reduced motion.
- Decision cards carry an icon (building, globe, departure) in a soft cyan square, and a light bloom on hover.
- Type scale: section headings now step up to about 2.15 rem on desktop so the page reads hero, section, card, not one flat size.
- Shape system: cards 16 px, tiles 14 px, panels and hero card 20 px, pills and buttons fully round. Square service cards remain only where the brand file calls for them.
- Motion: cards fade up 14 px as they enter the viewport, staggered 60 ms. Buttons and cards lift 1 to 2 px on hover. Everything is off under prefers-reduced-motion and in print.
- Diagnostic shows "n of 10 answered" with a progress bar.
- Mobile: the Calculate button is sticky at the bottom of the form; the working paper stacks label, value, then rule id; the nav button no longer wraps; action buttons sit in two columns.
- Arabic inherits all of it; bars, numbers and rule ids stay left-to-right inside right-to-left text.

## Next, for a designer

1. **A single visual idea.** The site is typographic and correct but has no image. One idea, used sparingly: a thin "working paper" ruled-line motif behind the hero, or an abstract line-chart glyph derived from the ob/co mark. Avoid stock photos of skylines.
2. **Icon set.** Eight to twelve line icons on a 24 px grid, 1.6 px stroke, for the calculators, services and journeys. The three on the home page set the style.
3. **Result panel as a document.** Treat the result as the first page of the PDF: a header band with jurisdiction, period and ruleset, then the number, then the working paper. Same hierarchy on screen and paper.
4. **Form rhythm.** Group labels at 0.8 rem small caps, 24 px between groups, 12 px within. Advanced sections collapsed by default with a one-line summary of what is inside.
5. **Colour discipline.** Cyan for navigation and links, green for the one action that produces a number, amber only for review-required, red never except errors. Audit the pages against that.
6. **Empty and loading states.** The leaderboard placeholder, the stale-result state and the "no open items" diagnostic each need a small illustration or at least a consistent card treatment.
7. **Arabic typography.** IBM Plex Sans Arabic is a safe pairing; a designer should set the Arabic display size one step smaller than Latin and check line-height on the hero.
8. **Photography of people, if any, only on the services page**, where a named team member stands next to the review offer.

## Checks before sign-off

Light and dark on every page; 320 px width; keyboard focus rings visible on the new cards; the reveal animation never hides content when JavaScript fails (it only applies once the script has run).
