import { HLJSApi } from 'highlight.js';
import * as Lucide from 'lucide';

declare global {
  interface Window {
    hljs?: HLJSApi;
    lucide?: typeof Lucide;
  }
}
