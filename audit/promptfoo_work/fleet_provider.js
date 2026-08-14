const fs = require("fs");
const path = require("path");
const RESP = JSON.parse(
  fs.readFileSync(path.join(__dirname, "responses.json"), "utf8"));
class FleetLookup {
  id() { return "fleet-lookup"; }
  async callApi(prompt, context) {
    const v = context.vars;
    const key = `${v.member}|${v.mode}|${v.i}`;
    if (!(key in RESP)) throw new Error("missing fleet response for " + key);
    return { output: RESP[key] };
  }
}
module.exports = FleetLookup;
