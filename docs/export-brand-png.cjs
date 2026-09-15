// 将 brand 目录下的 SVG 标识导出为 PNG 位图
// 用法：node docs/export-brand-png.cjs
const fs = require("fs");
const path = require("path");
const { Resvg } = require(process.env.RESVG_PATH ||
  "C:/Users/Fight/.workbuddy/binaries/node/workspace/node_modules/@resvg/resvg-js");

const BASE = path.join(__dirname, "..", "frontend", "public", "brand");
const OUT = path.join(BASE, "png");
fs.mkdirSync(OUT, { recursive: true });

const JOBS = [
  ["mark.svg", "mark-512.png", 512, null],
  ["mark.svg", "mark-256.png", 256, null],
  ["mark.svg", "mark-64.png", 64, null],
  ["logo-horizontal.svg", "logo-horizontal-1024.png", 1024, null],
  ["logo-horizontal.svg", "logo-horizontal-448.png", 448, null],
  ["logo-vertical.svg", "logo-vertical-320.png", 320, null],
  ["favicon.svg", "favicon-256.png", 256, null],
  ["mark-reverse.svg", "mark-reverse-512-on-ink.png", 512, "#23282B"],
  ["logo-horizontal-reverse.svg", "logo-horizontal-reverse-1024-on-ink.png", 1024, "#23282B"],
];

for (const [src, dst, width, background] of JOBS) {
  const svg = fs.readFileSync(path.join(BASE, src), "utf8");
  const opts = {
    fitTo: { mode: "width", value: width },
    font: { loadSystemFonts: true, defaultFontFamily: "SimSun" },
  };
  if (background) opts.background = background;
  const png = new Resvg(svg, opts).render().asPng();
  fs.writeFileSync(path.join(OUT, dst), png);
  console.log("ok", dst, png.length, "bytes");
}
console.log("done ->", OUT);
