// Keep the intro bounded and independent of model/runtime availability.
window.wixalLaunch = new Promise(resolve => {
  const screen = document.getElementById('launch-screen');
  const audio = document.getElementById('launch-audio');
  let finished = false, timeout, animations = [];
  const finish = () => {
    if (finished) return;
    finished = true;
    clearTimeout(timeout);
    animations.forEach(animation => animation.cancel());
    audio.pause();
    if (screen.open) screen.close();
    screen.remove();
    resolve();
  };
  screen.addEventListener('cancel', event => { event.preventDefault(); finish(); });
  // Also release startup if preference retrieval or rendering fails.
  timeout = setTimeout(finish, 3000);
  window.wixal.state().then(state => {
    if (finished) return;
    const ui = state.ui || {};
    document.documentElement.dataset.theme = ui.theme || 'sakura';
    document.getElementById('launch-version').textContent = state.appVersion ? `v${state.appVersion}` : '';
    const motion = ui.launchAnimation !== false && !ui.reduceMotion && !matchMedia('(prefers-reduced-motion: reduce)').matches;
    const start = () => {
      if (finished) return;
      if (ui.launchSound !== false) {
        audio.volume = 0.32;
        audio.play().catch(() => {}); // Audio failure must never delay startup.
      }
      if (!motion) {
        // Leave the short chime playing without holding the workspace behind an intro.
        finished = true;
        clearTimeout(timeout);
        screen.remove();
        resolve();
        return;
      }
      screen.showModal();
      animations = window.WixalLaunchMotion.play(screen.querySelector('.launch-scene'));
      clearTimeout(timeout);
      timeout = setTimeout(finish, window.WixalLaunchMotion.duration);
    };
    // Electron creates the window hidden; start when frames can actually be presented.
    requestAnimationFrame(start);
  }).catch(finish);
});
