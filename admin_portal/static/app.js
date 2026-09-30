document.addEventListener('DOMContentLoaded', () => {
  const toast = document.querySelector('[data-toast]');
  if (toast) setTimeout(() => toast.classList.add('fade-out'), 3800);

  const pitch = document.getElementById('pitch');
  const form = document.getElementById('formation-form');
  const output = document.getElementById('positions_json');
  if (!pitch || !form || !output) return;

  let dragged = null;
  const setPoint = (node, event) => {
    const box = pitch.getBoundingClientRect();
    const x = Math.max(2, Math.min(98, ((event.clientX - box.left) / box.width) * 100));
    const y = Math.max(12, Math.min(92, ((event.clientY - box.top) / box.height) * 100));
    node.style.left = `${x}%`; node.style.top = `${y}%`;
  };
  pitch.querySelectorAll('.player-node').forEach(node => {
    node.addEventListener('pointerdown', event => { dragged = node; node.setPointerCapture(event.pointerId); node.classList.add('dragging'); });
    node.addEventListener('pointermove', event => { if (dragged === node) setPoint(node, event); });
    node.addEventListener('pointerup', () => { node.classList.remove('dragging'); dragged = null; });
  });
  form.addEventListener('submit', () => {
    const positions = {};
    pitch.querySelectorAll('.player-node').forEach(node => {
      positions[node.dataset.slot] = { x: Number.parseFloat(node.style.left), y: Number.parseFloat(node.style.top) };
    });
    output.value = JSON.stringify(positions);
  });
});
