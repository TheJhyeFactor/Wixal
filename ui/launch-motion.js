/* Wixal's original folded wordmark reveal, played once at startup. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.WixalLaunchMotion = api;
})(globalThis, function () {
  'use strict';
  const duration = 2100;
  function play(scene, { exit = true, reduced = false } = {}) {
    scene.getAnimations({ subtree: true }).forEach(animation => animation.cancel());
    if (reduced || globalThis.matchMedia?.('(prefers-reduced-motion: reduce)').matches) return [];
    const animations = [];
    const animate = (selector, frames, delay, time, easing = 'cubic-bezier(.215,.61,.355,1)') => {
      const element = scene.querySelector(selector);
      if (!element) throw new Error('Missing Wixal wordmark element: ' + selector);
      animations.push(element.animate(frames, { delay, duration: time, easing, fill: 'both' }));
    };
    // Preserve the original logo's name-window/name-slide motion and exact vectors.
    animate('.launch-name-window', [{ width: '0px' }, { width: '285px' }], 180, 1020);
    animate('.launch-name-motion', [{ transform: 'translateX(-6px)' }, { transform: 'translateX(0)' }], 180, 1020);
    animate('.launch-fold', [{ opacity: 0 }, { opacity: 1 }], 230, 520);
    animate('.launch-name', [
      { opacity: 0, transform: 'translateY(7px) scale(.985)' },
      { opacity: 1, transform: 'translateY(0) scale(1)' }
    ], 0, 580);
    animate('.launch-version', [
      { opacity: 0, transform: 'translateY(4px)' },
      { opacity: 1, transform: 'translateY(0)' }
    ], 760, 420);
    if (exit) animations.push(scene.animate([
      { opacity: 1, transform: 'translateY(0)' },
      { opacity: 0, transform: 'translateY(-4px)' }
    ], { delay: duration - 220, duration: 200, easing: 'ease-in', fill: 'forwards' }));
    return animations;
  }
  return Object.freeze({ duration, play });
});
