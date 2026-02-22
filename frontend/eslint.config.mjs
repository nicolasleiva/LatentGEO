import nextVitals from "eslint-config-next/core-web-vitals";

const config = [
  {
    ignores: [
      "node_modules/**",
      ".cache/**",
      ".next/**",
      ".next_old/**",
      ".open-next/**",
      ".pnpm-store/**",
      "coverage/**",
      "dist/**",
      "build/**",
      "playwright-report/**",
      "test-results/**",
    ],
  },
  ...nextVitals,
  {
    rules: {
      "@next/next/no-html-link-for-pages": "off",
      "react-hooks/immutability": "off",
      "react-hooks/purity": "off",
      "react-hooks/set-state-in-effect": "off",
      "react-hooks/static-components": "off",
    },
  },
];

export default config;
