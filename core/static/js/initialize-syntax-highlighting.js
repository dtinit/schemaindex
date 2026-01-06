(() => {
  // https://json-schema.org/understanding-json-schema/keywords
  const JSON_SCHEMA_KEYWORDS = [
    '$anchor',
    '$comment',
    '$defs',
    '$dynamicAnchor',
    '$dynamicRef',
    '$id',
    '$ref',
    '$schema',
    '$vocabulary',
    'additionalProperties',
    'allOf',
    'anyOf',
    'const',
    'contains',
    'contentEncoding',
    'contentMediaType',
    'contentSchema',
    'default',
    'dependentRequired',
    'dependentSchemas',
    'deprecated',
    'description',
    'else',
    'enum',
    'examples',
    'exclusiveMaximum',
    'exclusiveMinimum',
    'format',
    'if',
    'items',
    'maxContains',
    'maximum',
    'maxItems',
    'maxLength',
    'maxProperties',
    'minContains',
    'minimum',
    'minItems',
    'minLength',
    'minProperties',
    'multipleOf',
    'not',
    'oneOf',
    'pattern',
    'patternProperties',
    'prefixItems',
    'properties',
    'propertyNames',
    'readOnly',
    'required',
    'then',
    'title',
    'type',
    'unevaluatedItems',
    'unevaluatedProperties',
    'uniqueItems',
    'writeOnly',
  ];

  /**
   * Augments Highlight.js's built-in JSON language
   * to specially highlight JSON Schema keywords.
   *
   * @import { HLJSApi } from 'highlight.js';
   * @param {HLJSApi} hljs
   */
  const jsonSchemaLanguage = (hljs) => {
    const jsonLanguage = hljs.getLanguage('json');
    if (!jsonLanguage) {
      throw new Error('Highlight.js is missing a definition for JSON');
    }
    const contains = jsonLanguage.contains.slice();
    contains.unshift({
      className: 'keyword',
      begin: new RegExp(
        `"(${JSON_SCHEMA_KEYWORDS.map((keyword) => keyword.replace('$', '\\$')).join('|')})"(?=\\s*:)`
      ),
      relevance: 2,
    });

    return Object.assign({}, jsonLanguage, {
      contains,
    });
  };

  document.addEventListener('DOMContentLoaded', () => {
    /**
     * @import { HLJSApi } from 'highlight.js';
     * @type Promise<HLJSApi>
     */
    const hljsPromise = new Promise((resolve, reject) => {
      if (window.hljs) {
        resolve(window.hljs);
        return;
      }
      const hljsScriptSrc = document.getElementById('hljs-src');
      if (!hljsScriptSrc) {
        reject(new Error('A Highlight.js script tag was not found.'));
        return;
      }
      hljsScriptSrc.addEventListener('load', () => {
        if (!window.hljs) {
          reject(new Error('Highlight.js failed to initialize.'));
          return;
        }
        resolve(window.hljs);
      });
    });
    hljsPromise
      .then((hljs) => {
        if (hljs.getLanguage('json')) {
          // Override the built-in definition for JSON with our
          // JSON schema-aware version.
          hljs.registerLanguage('json', jsonSchemaLanguage);
        }
        hljs.highlightAll();
      })
      .catch((err) => {
        console.error(err);
      });
  });
})();
