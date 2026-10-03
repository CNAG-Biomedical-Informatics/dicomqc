// JSDOM has no text layout; CodeMirror still requires the Range measurement APIs.
Range.prototype.getClientRects = () => [] as unknown as DOMRectList;
Range.prototype.getBoundingClientRect = () => new DOMRect();
