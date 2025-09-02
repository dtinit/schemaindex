interface WindowWithHljs extends Window {
  hljs: {
    highlightAll: () => void
  }
}
declare const window: WindowWithHljs;

export {}
