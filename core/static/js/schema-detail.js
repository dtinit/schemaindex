(() => {
  const hljsScriptSrc = document.getElementById('hljs-src');
  if (!hljsScriptSrc){
    return;
  }
  const hljsScriptSrcLoaded = new Promise((resolve) => {
    hljsScriptSrc.addEventListener('load', resolve);
  });
 
  const domContentLoaded = new Promise((resolve) => {
    document.addEventListener('DOMContentLoaded', resolve)
  });

  Promise.all([hljsScriptSrcLoaded, domContentLoaded]).then(() => {
    // TODO: figure out why we can't declare this in globals.d.ts
    /** @type window & {hljs: {highlightAll: () => void }} */ (window).hljs.highlightAll();
  });
})();
