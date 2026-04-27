/**
 * Module Loader — arxiv_recommender UI modules.
 *
 * Dependency order (enforced by script tag order in base_research.html):
 *   1. core.js          — AppState, I18N, shared utilities
 *   2. modals.js        — Modal open/close/confirm
 *   3. collections.js   — Collection CRUD and picker
 *   4. subscriptions.js — Query/Author subscription CRUD
 *   5. paper_actions.js — Queue, follow, download, paper action modal
 *   6. preferences.js   — Language/theme toggle (auto-initializes)
 *   7. app.js           — Bootstrap / cross-module coordination
 *
 * Inbox-specific logic (inbox.js) is loaded per-template via {% block scripts %}.
 *
 * All public functions are exported to window.* by their respective modules
 * so that inline onclick / onchange handlers in templates continue to work.
 */
(function () {
  // Verify all modules are loaded
  if (typeof window.showToast !== 'function') {
    console.warn('core.js not loaded — showToast missing');
  }
  if (typeof window.openModal !== 'function') {
    console.warn('modals.js not loaded — openModal missing');
  }
  if (typeof window.openCollectionPicker !== 'function') {
    console.warn('collections.js not loaded — openCollectionPicker missing');
  }
  if (typeof window.openQuerySubscriptionModal !== 'function') {
    console.warn('subscriptions.js not loaded — openQuerySubscriptionModal missing');
  }
  if (typeof window.queuePaperStatus !== 'function') {
    console.warn('paper_actions.js not loaded — queuePaperStatus missing');
  }
  if (typeof window.applyLanguage !== 'function') {
    console.warn('preferences.js not loaded — applyLanguage missing');
  }
})();
