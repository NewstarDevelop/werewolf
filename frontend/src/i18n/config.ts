import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';
import Backend from 'i18next-http-backend';

// Initialize i18next with React integration
i18n
  .use(Backend)  // Load translations from public/locales
  .use(LanguageDetector)  // Detect user language preference
  .use(initReactI18next)  // React binding
  .init({
    lng: 'zh',  // 强制初始化语言为中文
    fallbackLng: 'zh',  // Default to Chinese
    supportedLngs: ['zh', 'en'],  // Supported languages
    defaultNS: 'common',  // Default namespace

    backend: {
      // Path to translation files
      loadPath: '/locales/{{lng}}/{{ns}}.json',
      requestOptions: {
        cache: 'no-store',
      },
    },

    interpolation: {
      escapeValue: false,  // React already handles XSS
    },

    detection: {
      // Language detection order: localStorage > navigator language
      order: ['localStorage', 'navigator'],
      caches: ['localStorage'],  // Cache language preference
      lookupLocalStorage: 'i18nextLng',
    },

    react: {
      useSuspense: true,  // 启用 Suspense，配合按需加载
      bindI18n: 'languageChanged loaded',
      bindI18nStore: 'added removed',
    },

    // Development mode settings
    debug: import.meta.env.DEV,
  });

// 调试事件监听
if (import.meta.env.DEV) {
  i18n.on('initialized', (options) => {
    console.log('[i18n] Initialized:', options);
  });

  i18n.on('loaded', (loaded) => {
    console.log('[i18n] Loaded:', loaded);
  });

  i18n.on('failedLoading', (lng, ns, msg) => {
    console.error('[i18n] Failed loading:', lng, ns, msg);
  });

  i18n.on('languageChanged', (lng) => {
    console.log('[i18n] Language changed to:', lng);
  });
}

// Update html lang attribute on language change
i18n.on('languageChanged', (lng) => {
  document.documentElement.lang = lng;
});

// Set initial language
if (i18n.language) {
  document.documentElement.lang = i18n.language;
}

export default i18n;
