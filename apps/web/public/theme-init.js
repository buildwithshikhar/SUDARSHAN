// Applies the stored theme and language before the first paint, so there is no flash of the
// default theme. Keep the keys in step with src/lib/prefs.ts and src/i18n/index.ts.
try {
  var theme = window.localStorage.getItem('ui.theme')
  if (theme === 'light' || theme === 'dark') document.documentElement.dataset.theme = theme
  var language = window.localStorage.getItem('ui.language')
  if (language === 'hi' || language === 'en') document.documentElement.lang = language
} catch (error) {
  /* storage blocked: the defaults apply */
}
