// Some headless/misconfigured environments report an invalid navigator.language
// (e.g. "en-US@posix"). uPlot passes it to Intl.NumberFormat at MODULE INIT, which
// throws and kills the whole bundle. Sanitize: fall back to en-US on invalid tags.
// This module must be the FIRST import of the entry point.
const OrigNF = Intl.NumberFormat;

function SafeNF(this: unknown, locales?: string | string[], options?: Intl.NumberFormatOptions) {
  try {
    return new OrigNF(locales, options);
  } catch {
    return new OrigNF("en-US", options);
  }
}
SafeNF.prototype = OrigNF.prototype;
SafeNF.supportedLocalesOf = OrigNF.supportedLocalesOf;

// eslint-disable-next-line @typescript-eslint/no-explicit-any
(Intl as any).NumberFormat = SafeNF;

export {};
