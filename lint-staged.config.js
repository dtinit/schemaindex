module.exports = {
  'core/static/**/*.js': ['eslint --fix', () => 'tsc', 'prettier --write'],
  '{README,contribute}.md': ['prettier --write'],
  'core/static/**/*.css': ['prettier --write'],
};
