import { HLJSApi } from 'highlight.js';

declare global {
  interface Window {
    hljs?: HLJSApi;
  }
}
