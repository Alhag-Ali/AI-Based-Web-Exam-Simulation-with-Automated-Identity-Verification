const webpack = require('webpack');
const path = require('path');

module.exports = function override(config, env) {
  // Fallbacks für Node.js Module (für axios 1.x)
  config.resolve.fallback = {
    ...config.resolve.fallback,
    "http": require.resolve("stream-http"),
    "https": require.resolve("https-browserify"),
    "stream": require.resolve("stream-browserify"),
    "util": require.resolve("util"),
    "url": require.resolve("url"),
    "zlib": require.resolve("browserify-zlib"),
    "crypto": require.resolve("crypto-browserify"),
    "process": require.resolve("process/browser.js"),
  };
  
  // Alias für process/browser
  config.resolve.alias = {
    ...config.resolve.alias,
    "process": path.resolve(__dirname, "node_modules/process/browser.js"),
  };
  
  // ProvidePlugin für process und Buffer
  config.plugins = [
    ...config.plugins,
    new webpack.ProvidePlugin({
      process: path.resolve(__dirname, "node_modules/process/browser.js"),
      Buffer: ["buffer", "Buffer"],
    }),
    // NormalModuleReplacementPlugin um process/browser richtig aufzulösen
    new webpack.NormalModuleReplacementPlugin(
      /^process\/browser$/,
      path.resolve(__dirname, "node_modules/process/browser.js")
    ),
  ];
  
  return config;
};

