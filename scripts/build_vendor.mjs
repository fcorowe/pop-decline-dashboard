import { readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { build } from "esbuild";

const root = fileURLToPath(new URL("../", import.meta.url));
const { metafile } = await build({
  absWorkingDir: root,
  stdin: {
    resolveDir: root,
    contents: `
      export { extent, max, median, min, rollup } from "d3-array";
      export { color } from "d3-color";
      export { format } from "d3-format";
      export { geoAzimuthalEqualArea, geoDistance, geoGraticule, geoPath } from "d3-geo";
      export { interpolateRgb } from "d3-interpolate";
      export { scaleBand, scaleLinear } from "d3-scale";
      export { select, selectAll } from "d3-selection";
      export { curveMonotoneX, line, stack } from "d3-shape";
      import "d3-transition";
      export { zoom, zoomIdentity } from "d3-zoom";
    `,
  },
  outfile: "site/vendor/d3.min.js",
  globalName: "d3",
  format: "iife",
  bundle: true,
  minify: true,
  metafile: true,
  banner: { js: "/*! D3 modules and dependencies. See D3-LICENSE.txt. */" },
});

const packages = [...new Set(Object.keys(metafile.inputs)
  .filter((path) => path.startsWith("node_modules/"))
  .map((path) => path.split("/")[1]))].sort();
const licences = await Promise.all(packages.map(async (name) => {
  const directory = new URL(`../node_modules/${name}/`, import.meta.url);
  return `${name}\n${(await readFile(new URL("LICENSE", directory), "utf8")).trim()}`;
}));
await writeFile(new URL("../site/vendor/D3-LICENSE.txt", import.meta.url), licences.join("\n\n") + "\n");
