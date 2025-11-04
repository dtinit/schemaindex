const js = require('@eslint/js');
const globals = require('globals');
const prettier = require('eslint-config-prettier');

module.exports = [
  {
    ignores: ['env'],
  },
  js.configs.recommended,
  prettier,
  {
    files: ['*.js'],
    languageOptions: {
      globals: globals.node,
    },
  },
  {
    files: ['core/static/**/*.js'],
    languageOptions: {
      ecmaVersion: 2015,
      sourceType: 'script',
      globals: globals.browser,
    },
    rules: {
      'no-implicit-globals': ['error', { lexicalBindings: true }],
    },
  },
];

