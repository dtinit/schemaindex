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

1. Create a `ul` element for the formset elements with the attribute `data-formset-list-id="<Some list id>"`.
2. Render the formset's `empty_form` somewhere on the page inside an element with the attribute `data-formset-template-for-id="<The list id>"`.
3. To use buttons to add and remove formset items to and from the formset, use the attribute `data-formset-append-to-list-id="<The list id>"` on the append button and `data-formset-remove-from-list-id="<The list id>"` on the remove button.

### JavaScript typechecking with TypeScript

We use TypeScript JSDoc annotations to add type safety to our JavaScript files. That said, we don't currently run typechecking as any sort of build or validation process and it's moreso just used as a development aid. We'll probably enforce type safety in the future.

To get type checking feedback in your code editor, [check here](https://github.com/microsoft/TypeScript/wiki/TypeScript-Editor-Support) for instructions for your editor. The configuration file is named [tsconfig.json](tsconfig.json), but your editor will probably find it for you.

Note that we only use TypeScript to *type check* our JavaScript files; we do not *transpile* from TypeScript to JavaScript. Don't try to write any TypeScript in this repository (except for declaration files like [globals.d.ts](globals.d.ts)). Check out the [TypeScript JSDoc Reference](https://www.typescriptlang.org/docs/handbook/jsdoc-supported-types.html) to learn how to leverage types in JavaScript files.

### Stylesheets

We use the CSS reset/normalizer from Tailwind named [preflight.css](core/static/css/preflight.css) which is fairly aggressive. Otherwise, all site styles are defined in [site.css](core/static/css/site.css) with global styles at the top and page styles at the bottom. We try to use BEM syntax where appropriate; for example, we have a `.button` class with modifiers like `.button--prominent` and `.button--danger`.
