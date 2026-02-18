/** @type {import('next-i18next').UserConfig} */
module.exports = {
  i18n: {
    defaultLocale: "en",
    locales: ["en", "es"],
  },
  defaultNS: "common",
  localePath: "./public/locales",
  reloadOnPrerender: process.env.NODE_ENV === "development",
  detection: {
    order: ["cookie", "htmlTag", "navigator"],
    caches: ["cookie"],
  },
  // Ensure English is always used for enterprise consistency
  load: "currentOnly",
  // Override the default locale detection to always use English
  localeDetection: false,
};
