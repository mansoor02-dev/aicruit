// Stub for @asamuzakjp/css-color to avoid ESM/CJS interop crash in jsdom 27 on Node 20.
// jsdom only uses this for advanced CSS color resolution; our tests don't depend on it.
'use strict';

const passthrough = (s) => (typeof s === 'string' ? s : '');
const noop = () => '';

module.exports = {
  convert: passthrough,
  resolve: passthrough,
  parse: () => null,
  serialize: passthrough,
  cssCalc: noop,
  isColor: () => false,
  isGradient: () => false,
  resolveColor: passthrough,
  resolveGradient: passthrough,
};
