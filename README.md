# Schemas.Pub

A public schema registry.

## Local setup

To run locally, you'll first need to install Python and pip.

To install project dependencies with pip, run `pip install -r requirements.txt`.

To access the database management portal, create a superuser for yourself with `python3 manage.py createsuperuser`.

To start the project, run `python3 manage.py runserver`.

During local development, emails will output to the console instead of actually sending.

## Utilites

### Formsets

We have JavaScript support for dynamic formsets as part of a form. For an example, see the "additional documentation" section of the [schema management form](core/templates/core/manage/schema.html).

1. Pass a custom `prefix` to the formset, e.g: `formset = FormsetFactory(prefix="<Some custom formset id>")`.
2. Create a `ul` element for the formset elements with the attribute `data-formset-list-id="<The formset prefix>"`.
3. Render the formset's `empty_form` somewhere on the page inside an element with the attribute `data-formset-template-for-id="<The formset prefix>"`.
4. To use buttons to add and remove formset items to and from the formset, use the attribute `data-formset-append-to-list-id="<The formset prefix>"` on the append button and `data-formset-remove-from-list-id="<The formset prefix>"` on the remove button.

### Stylesheets

We use the CSS reset/normalizer from Tailwind named [preflight.css](core/static/css/preflight.css) which is fairly aggressive. Otherwise, all site styles are defined in [site.css](core/static/css/site.css) with global styles at the top and page styles at the bottom. We try to use BEM syntax where appropriate; for example, we have a `.button` class with modifiers like `.button--prominent` and `.button--danger`.

## Frontend dev tooling

Frontend dev tools like ESLint are delivered via [npm](https://www.npmjs.com/), which is included with Node.js. To use the tools locally, you'll need to:

1. Install [Node.js](https://nodejs.org).
2. Run `npm install` wherever you cloned this repository to.

### Linting with ESLint

You can run the linter by executing `npm run lint`. If there are no issues, there won't be any output.

To get linting feedback in your code editor, [check here](https://eslint.org/docs/latest/use/integrations) to find an ESLint integration or instructions for your editor. The configuration file is named [eslint.config.js](eslint.config.js), but your editor/plugin should find it for you.

### Formatting with Prettier

You can format JavaScript and CSS files with `npm run format`.

To enable formatting from your code editor, [check here](https://prettier.io/docs/en/editors) for instructions for your editor. The configuration is in [package.json](package.json), but your editor/plugin should find it for you.

### Typechecking with TypeScript

You can check JavaScript types with `npm run typecheck`.

To get type checking feedback in your code editor, [check here](https://github.com/microsoft/TypeScript/wiki/TypeScript-Editor-Support) for instructions for your editor. The configuration file is named [tsconfig.json](tsconfig.json), but your editor/plugin should find it for you.

Note that we only use TypeScript to _type check_ our JavaScript files; we do not _transpile_ from TypeScript to JavaScript. Don't try to write any TypeScript in this repository (except for declaration files like [globals.d.ts](globals.d.ts)). Check out the [TypeScript JSDoc Reference](https://www.typescriptlang.org/docs/handbook/jsdoc-supported-types.html) to learn how to leverage types in JavaScript files.

### Precommit checks/fixes

When commiting relevant files with git, the following steps are performed:

- JavaScript files are linted, typechecked, and formatted. If issues are found, your commit will fail; please correct your issues and try again.
- README.md and CSS files are formatted.
