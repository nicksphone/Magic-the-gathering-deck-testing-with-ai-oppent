// Serializable: evaluate this function in the page; it captures no module state.
export async function visibleCardPoint(selector) {
  const node = document.querySelector(selector);
  if (!node) throw new Error('Missing card: ' + selector);
  node.scrollIntoView({block: 'center', inline: 'nearest'});
  await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  const box = node.getBoundingClientRect();
  const left = Math.max(0, box.left), right = Math.min(innerWidth, box.right);
  const top = Math.max(0, box.top), bottom = Math.min(innerHeight, box.bottom);
  if (right <= left || bottom <= top) throw new Error('Card is outside the viewport: ' + selector);
  for (const fy of [0.5, 0.25, 0.75, 0.1, 0.9]) {
    for (const fx of [0.5, 0.25, 0.75, 0.1, 0.9]) {
      const x = left + (right - left) * fx, y = top + (bottom - top) * fy;
      const hit = document.elementFromPoint(x, y);
      if (hit && node.contains(hit)
        && !hit.closest('button,input,select,a,summary,.combat-toolbar,.turn-command-bar,.table-navigation')) {
        return {x, y};
      }
    }
  }
  throw new Error('No unobscured non-control card point: ' + selector);
}
