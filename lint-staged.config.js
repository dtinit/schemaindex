module.exports = {
  'core/static/**/*.js': ['eslint --fix', () => 'tsc', 'prettier --write'],
  'README.md': ['prettier --write'],
  'core/static/**/*.css': ['prettier --write'],
};
