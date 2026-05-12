// static/js/sidebar.js
// Sidebar collapse/expand and mobile hamburger behavior
(function () {
  'use strict';

  var STORAGE_KEY = 'statdesk.sidebar.collapsed';

  function initSidebar() {
    var sidebar = document.getElementById('sidebar');
    if (!sidebar) return;
    var collapsed = localStorage.getItem(STORAGE_KEY) === 'true';
    sidebar.dataset.collapsed = String(collapsed);
  }

  function toggleSidebar() {
    var sidebar = document.getElementById('sidebar');
    if (!sidebar) return;
    var next = sidebar.dataset.collapsed !== 'true';
    sidebar.dataset.collapsed = String(next);
    localStorage.setItem(STORAGE_KEY, String(next));
  }

  // Mobile hamburger
  function toggleMobileSidebar() {
    var sidebar = document.getElementById('sidebar');
    if (!sidebar) return;
    sidebar.classList.toggle('is-open');
  }

  document.addEventListener('DOMContentLoaded', initSidebar);

  window.toggleSidebar = toggleSidebar;
  window.toggleMobileSidebar = toggleMobileSidebar;
})();
