/* Small progressive enhancements; website also works without JavaScript. */
document.querySelectorAll('[data-close-flash]').forEach(button => {
  button.addEventListener('click', () => button.closest('.flash')?.remove());
});
document.querySelectorAll('[data-confirm-delete]').forEach(form => {
  form.addEventListener('submit', event => {
    if (!window.confirm('Delete this note? This cannot be undone.')) event.preventDefault();
  });
});
const contentInput = document.querySelector('#content');
const counter = document.querySelector('[data-character-count]');
if (contentInput && counter) {
  const updateCount = () => { counter.textContent = `${contentInput.value.length} / 4000`; };
  contentInput.addEventListener('input', updateCount);
  updateCount();
}
