(() => {
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
      .then((hljs) => hljs.highlightAll())
      .catch((err) => {
        console.error(err);
      });
  });
})();
