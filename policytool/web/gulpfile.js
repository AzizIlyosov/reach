const { 
  dest,
  parallel,
  src,
  pipe,
  watch
} = require('gulp');

exports.css = function() {
  const postcss = require('gulp-postcss');
  const sourcemaps = require('gulp-sourcemaps');
  const url = require('postcss-url');

  const plugins = [
        require('precss'),
        require('autoprefixer'),
        require('postcss-import'),
        url({url: "inline"}), // Inline font URLs in our CSS
        require('cssnano')
  ];

  return src('static/**/*.css')
    .pipe( sourcemaps.init() )
    .pipe( postcss(plugins) )
    // sourcemaps get written to build/static anyway
    .pipe( sourcemaps.write('.') )
    .pipe( dest('build/static') );
};

exports.default = parallel(exports.css);

exports.watch = function() {
  watch('static/*.css', {ignoreInitial: false}, exports.css);
};