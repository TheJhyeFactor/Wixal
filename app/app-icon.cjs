const path = require('node:path');

const choices = ['theme', 'sakura', 'midnight', 'pearl', 'copper'];
const themeIcons = { sakura: 'sakura', midnight: 'midnight', forest: 'copper', paper: 'pearl' };
function resolveIcon(ui = {}) {
  return choices.includes(ui.appIcon) && ui.appIcon !== 'theme' ? ui.appIcon : themeIcons[ui.theme] || 'sakura';
}
function iconPath(ui) {
  return path.join(__dirname, '../assets/icon-variants', `${resolveIcon(ui)}.png`);
}
module.exports = { choices, resolveIcon, iconPath };
