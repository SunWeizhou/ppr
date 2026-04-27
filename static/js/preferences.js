(function () {
  function applyLanguage(language) {
    const lang = window.I18N[language] ? language : 'zh';
    document.documentElement.dataset.language = lang;
    document.documentElement.lang = lang === 'zh' ? 'zh-CN' : 'en';
    const i18nMap = window.I18N[lang] || {};
    document.querySelectorAll('[data-i18n], [data-i18n-quote]').forEach(function (node) {
      const key = node.dataset.i18n || node.dataset.i18nQuote;
      if (i18nMap[key]) node.textContent = i18nMap[key];
    });
    const languageToggle = document.querySelector('[data-action="toggle-language"]');
    if (languageToggle) languageToggle.textContent = lang === 'zh' ? '中 / EN' : 'EN / 中';
    localStorage.setItem('statdesk.language', lang);
  }

  function applyTheme(theme) {
    const nextTheme = theme === 'dark' ? 'dark' : 'light';
    document.documentElement.dataset.theme = nextTheme;
    const themeToggle = document.querySelector('[data-action="toggle-theme"]');
    if (themeToggle) themeToggle.textContent = nextTheme === 'dark' ? 'Light' : 'Dark';
    localStorage.setItem('statdesk.theme', nextTheme);
  }

  function initPreferences() {
    const storedLanguage = localStorage.getItem('statdesk.language') || 'zh';
    const storedTheme = localStorage.getItem('statdesk.theme') || 'light';
    applyLanguage(storedLanguage);
    applyTheme(storedTheme);
    document.querySelector('[data-action="toggle-language"]')?.addEventListener('click', function () {
      applyLanguage(document.documentElement.dataset.language === 'zh' ? 'en' : 'zh');
    });
    document.querySelector('[data-action="toggle-theme"]')?.addEventListener('click', function () {
      applyTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark');
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initPreferences);
  } else {
    initPreferences();
  }

  Object.assign(window, {
    applyLanguage: applyLanguage,
    applyTheme: applyTheme
  });
})();
