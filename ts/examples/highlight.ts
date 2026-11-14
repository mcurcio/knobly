// Sample "highlight" (examples/samples.json; TypeScript only, like knobly/highlight): class every token of a text for
// an editor's highlighting, with no antlr4 in the bundle. ts/examples/examples.test.ts runs this file and compares
// what it prints with examples/expected/highlight.txt.
// --8<-- [start:main]
import { highlight, HighlightClass } from "knobly/highlight";

const text = '@set $port 8080;\nserver {\n    listen $port;  # all hosts\n    name "a" -x;\n    oops "open\n}\n';

// Wrap each span in a <span> with a class an editor's theme styles: kn-directive, kn-variable, ...
const html = highlight(text)
  .map((span) => {
    const part = text.slice(span.start, span.end).replaceAll("&", "&amp;").replaceAll("<", "&lt;");
    return span.class === HighlightClass.Space ? part : `<span class="kn-${span.class}">${part}</span>`;
  })
  .join("");
console.log(html);

const spans = highlight(text);
console.log(`spans ${spans.length}, lossless ${spans.map((s) => text.slice(s.start, s.end)).join("") === text}`);
// --8<-- [end:main]
