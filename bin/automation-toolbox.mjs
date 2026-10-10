#!/usr/bin/env node
// Install the f3i Automation Toolbox's skills and agents into Claude Code.
//
//   npx github:F3-Insights/automation-toolbox list
//   npx github:F3-Insights/automation-toolbox install finance strategy
//   npx github:F3-Insights/automation-toolbox install --skill pre-mortem
//   npx github:F3-Insights/automation-toolbox install --all
//   npx github:F3-Insights/automation-toolbox uninstall
//
// Skills are copied to <target>/skills/<skill>/ and agents to
// <target>/agents/<department>/<agent>.md, the layout setup/link.py builds, so the
// script paths the skills use (~/.claude/skills/<skill>/scripts/...) resolve.
// The target is ~/.claude by default, ./.claude with --project, or --target DIR.
//
// Safety: nothing outside the target is touched; a skill or agent that is already
// there and was not installed by this tool is skipped unless --force; a record of
// what was installed (.f3i-toolbox.json in the target) lets update and uninstall
// remove only what this tool put there. No network access, no dependencies.

import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const PKG = JSON.parse(fs.readFileSync(path.join(ROOT, "package.json"), "utf8"));
const MANIFEST = ".f3i-toolbox.json";
const SKIP_DIRS = new Set(["tests", "__pycache__", ".pytest_cache", "node_modules"]);
const PYTHON_PACKAGES = "pyyaml openpyxl python-pptx pypdf pillow";
const REPO = "github:F3-Insights/automation-toolbox";

// ---------------------------------------------------------------- catalog

function readDescription(file) {
  const text = fs.readFileSync(file, "utf8");
  const m = text.match(/^---\n([\s\S]*?)\n---/);
  const d = m && m[1].match(/^description:\s*"?(.*?)"?\s*$/m);
  return d ? d[1] : "";
}

function catalog() {
  const departments = [];
  for (const name of fs.readdirSync(ROOT).sort()) {
    const dir = path.join(ROOT, name);
    if (name.startsWith(".") || !fs.statSync(dir).isDirectory()) continue;
    const agentsDir = path.join(dir, "agents");
    const skillsDir = path.join(dir, "skills");
    if (!fs.existsSync(agentsDir) && !fs.existsSync(skillsDir)) continue;
    const agents = fs.existsSync(agentsDir)
      ? fs.readdirSync(agentsDir).filter((f) => f.endsWith(".md")).sort()
          .map((f) => ({ name: f.slice(0, -3), file: path.join(agentsDir, f) }))
      : [];
    const skills = fs.existsSync(skillsDir)
      ? fs.readdirSync(skillsDir).sort()
          .filter((s) => fs.existsSync(path.join(skillsDir, s, "SKILL.md")))
          .map((s) => ({ name: s, dir: path.join(skillsDir, s) }))
      : [];
    departments.push({ name, agents, skills });
  }
  return departments;
}

function textOf(dir) {
  let out = "";
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (SKIP_DIRS.has(entry.name)) continue;
    const p = path.join(dir, entry.name);
    if (entry.isDirectory()) out += textOf(p);
    else if (/\.(md|py|yaml|yml|toml|json|sh)$/.test(entry.name)) out += fs.readFileSync(p, "utf8") + "\n";
  }
  return out;
}

// Skills refer to each other by name. Hard references (a skill listed in frontmatter
// `skills:`, or a script run by its ~/.claude/skills/<name>/ path) are followed all the
// way down. A backticked name is followed only from the pieces chosen, one level, since
// prose also names skills to say "use that one instead".
function frontmatterSkills(text) {
  const fm = text.match(/^---\n([\s\S]*?)\n---/);
  if (!fm) return [];
  const m = fm[1].match(/^skills:\s*(.*)$((?:\n\s+-\s*.+)*)/m);
  if (!m) return [];
  return (m[1] + m[2]).split(/[\n,\[\]]/).map((s) => s.replace(/^\s*-\s*/, "").trim()).filter(Boolean);
}

function hardRefs(text, names) {
  const found = new Set(frontmatterSkills(text));
  for (const m of text.matchAll(/skills\/([a-z0-9-]+)\//g)) found.add(m[1]);
  return [...found].filter((n) => names.has(n));
}

function withDependencies(chosen, allSkills, chosenAgents) {
  const byName = new Map(allSkills.map((s) => [s.name, s]));
  const names = new Set(byName.keys());
  const result = new Map(chosen.map((s) => [s.name, s]));
  const chosenTexts = [...chosen.map((s) => textOf(s.dir)), ...chosenAgents.map((a) => fs.readFileSync(a.file, "utf8"))];
  const queue = [];
  const add = (name) => {
    if (result.has(name)) return;
    result.set(name, byName.get(name));
    queue.push(textOf(byName.get(name).dir));
  };
  for (const text of chosenTexts) {
    for (const name of hardRefs(text, names)) add(name);
    for (const m of text.matchAll(/`([a-z0-9-]+)`/g)) if (names.has(m[1])) add(m[1]);
    queue.push(text);
  }
  while (queue.length) for (const name of hardRefs(queue.pop(), names)) add(name);
  return [...result.values()];
}

// ---------------------------------------------------------------- file helpers

function copyDir(src, dest) {
  fs.mkdirSync(dest, { recursive: true });
  for (const entry of fs.readdirSync(src, { withFileTypes: true })) {
    if (SKIP_DIRS.has(entry.name)) continue;
    const from = path.join(src, entry.name);
    const to = path.join(dest, entry.name);
    if (entry.isDirectory()) copyDir(from, to);
    else if (entry.isFile()) {
      fs.copyFileSync(from, to);
      if (from.endsWith(".py") || from.endsWith(".sh")) fs.chmodSync(to, 0o755);
    }
  }
}

function readManifest(target) {
  const file = path.join(target, MANIFEST);
  if (!fs.existsSync(file)) return { version: null, skills: [], agents: [] };
  return JSON.parse(fs.readFileSync(file, "utf8"));
}

function writeManifest(target, manifest) {
  fs.writeFileSync(path.join(target, MANIFEST), JSON.stringify(manifest, null, 2) + "\n");
}

const count = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;

function tilde(p) {
  const home = os.homedir();
  return p.startsWith(home) ? "~" + p.slice(home.length) : p;
}

// ---------------------------------------------------------------- arguments

function parse(argv) {
  const opts = { command: argv[0] || "help", names: [], skills: [], all: false, force: false, dryRun: false,
    agents: true, target: path.join(os.homedir(), ".claude") };
  for (let i = 1; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--all") opts.all = true;
    else if (a === "--force") opts.force = true;
    else if (a === "--dry-run") opts.dryRun = true;
    else if (a === "--no-agents") opts.agents = false;
    else if (a === "--project") opts.target = path.resolve(".claude");
    else if (a === "--target") opts.target = path.resolve(argv[++i].replace(/^~(?=$|\/)/, os.homedir()));
    else if (a === "--skill") opts.skills.push(argv[++i]);
    else if (a.startsWith("-")) fail(`unknown option ${a}; run with "help"`);
    else opts.names.push(a);
  }
  return opts;
}

function fail(message) {
  console.error(`automation-toolbox: ${message}`);
  process.exit(2);
}

// ---------------------------------------------------------------- commands

function help() {
  console.log(`f3i Automation Toolbox ${PKG.version}: skills and agents for Claude Code

Usage:
  npx ${REPO} list                         departments, with their agents and skills
  npx ${REPO} list <department>            the agents and skills in one department
  npx ${REPO} install <department>...      install whole departments
  npx ${REPO} install --skill <name>       install one skill (repeatable)
  npx ${REPO} install --all                install everything
  npx ${REPO} status                       what this tool has installed
  npx ${REPO} uninstall                    remove everything this tool installed

Options:
  --project        install into ./.claude (this project) instead of ~/.claude
  --target DIR     install into DIR instead of ~/.claude
  --no-agents      install skills only
  --force          replace a skill or agent this tool did not install
  --dry-run        show what would change, change nothing

Skills a piece depends on are installed with it. Run install again to update.
Docs: https://github.com/F3-Insights/automation-toolbox#install`);
}

function list(opts) {
  const departments = catalog();
  if (opts.names.length) {
    for (const name of opts.names) {
      const d = departments.find((x) => x.name === name) || fail(`no department "${name}"`);
      console.log(`\n${d.name}: ${d.agents.length} agents, ${d.skills.length} skills\n`);
      for (const s of d.skills) console.log(`  skill  ${s.name.padEnd(38)} ${readDescription(path.join(s.dir, "SKILL.md")).slice(0, 90)}`);
      for (const a of d.agents) console.log(`  agent  ${a.name}`);
    }
    return;
  }
  console.log("\nDepartment              Agents  Skills");
  for (const d of departments) console.log(`${d.name.padEnd(24)}${String(d.agents.length).padStart(6)}  ${String(d.skills.length).padStart(6)}`);
  console.log(`\nInstall one with: npx ${REPO} install <department>`);
}

function install(opts) {
  const departments = catalog();
  const allSkills = departments.flatMap((d) => d.skills);
  let skills = [];
  let agents = [];
  if (opts.all) {
    skills = allSkills;
    agents = departments.flatMap((d) => d.agents.map((a) => ({ ...a, department: d.name })));
  }
  for (const name of opts.names) {
    const d = departments.find((x) => x.name === name) || fail(`no department "${name}"; run "list"`);
    skills.push(...d.skills);
    agents.push(...d.agents.map((a) => ({ ...a, department: d.name })));
  }
  for (const name of opts.skills) skills.push(allSkills.find((s) => s.name === name) || fail(`no skill "${name}"`));
  if (!skills.length && !agents.length) fail('name a department, --skill <name> or --all; run "list" to see them');
  if (!opts.agents) agents = [];
  const chosen = new Set(skills.map((s) => s.name));
  skills = withDependencies([...new Map(skills.map((s) => [s.name, s])).values()], allSkills, agents);
  const extra = skills.filter((s) => !chosen.has(s.name)).map((s) => s.name);

  const skillsRoot = path.join(opts.target, "skills");
  const agentsRoot = path.join(opts.target, "agents");
  for (const root of [skillsRoot, agentsRoot]) {
    if (fs.existsSync(root) && fs.lstatSync(root).isSymbolicLink())
      fail(`${tilde(root)} is a link (set up by setup/link.py from a clone). Update with "git pull" in the clone instead.`);
  }
  const manifest = readManifest(opts.target);
  const owned = { skills: new Set(manifest.skills), agents: new Set(manifest.agents) };
  const done = { skills: [], agents: [], skipped: [] };

  for (const s of skills) {
    const dest = path.join(skillsRoot, s.name);
    if (fs.existsSync(dest) && !owned.skills.has(s.name) && !opts.force) { done.skipped.push(`skill ${s.name}`); continue; }
    if (!opts.dryRun) { fs.rmSync(dest, { recursive: true, force: true }); copyDir(s.dir, dest); }
    done.skills.push(s.name);
  }
  for (const a of agents) {
    const rel = path.join(a.department, `${a.name}.md`);
    const dest = path.join(agentsRoot, rel);
    if (fs.existsSync(dest) && !owned.agents.has(rel) && !opts.force) { done.skipped.push(`agent ${rel}`); continue; }
    if (!opts.dryRun) { fs.mkdirSync(path.dirname(dest), { recursive: true }); fs.copyFileSync(a.file, dest); }
    done.agents.push(rel);
  }
  if (!opts.dryRun) {
    writeManifest(opts.target, {
      version: PKG.version,
      installed: new Date().toISOString(),
      skills: [...new Set([...manifest.skills, ...done.skills])].sort(),
      agents: [...new Set([...manifest.agents, ...done.agents])].sort(),
    });
  }

  const verb = opts.dryRun ? "Would install" : "Installed";
  console.log(`${verb} ${count(done.skills.length, "skill")} and ${count(done.agents.length, "agent")} into ${tilde(opts.target)}`);
  if (extra.length) console.log(`  including ${count(extra.length, "skill")} they depend on: ${extra.join(", ")}`);
  if (done.skipped.length) console.log(`  skipped ${done.skipped.length} already there and not installed by this tool (use --force to replace): ${done.skipped.join(", ")}`);
  if (!opts.dryRun) {
    console.log(`
Next steps:
  1. Restart Claude Code so it picks up the new skills and agents.
  2. Scripts run with python3 (3.11 or later). Some need: pip install ${PYTHON_PACKAGES}
  3. Add your settings to ~/.config/f3i-toolbox/settings.toml when a skill asks:
     https://github.com/F3-Insights/automation-toolbox/blob/main/docs/settings.md`);
  }
}

function status(opts) {
  const m = readManifest(opts.target);
  if (!m.version) return console.log(`Nothing installed by this tool in ${tilde(opts.target)}.`);
  console.log(`${tilde(opts.target)}: version ${m.version}, installed ${m.installed}`);
  console.log(`  ${count(m.skills.length, "skill")}, ${count(m.agents.length, "agent")} (run "install" again to update)`);
}

function uninstall(opts) {
  const m = readManifest(opts.target);
  if (!m.version) return console.log(`Nothing installed by this tool in ${tilde(opts.target)}.`);
  for (const s of m.skills) if (!opts.dryRun) fs.rmSync(path.join(opts.target, "skills", s), { recursive: true, force: true });
  for (const a of m.agents) {
    const file = path.join(opts.target, "agents", a);
    if (opts.dryRun) continue;
    fs.rmSync(file, { force: true });
    const dir = path.dirname(file);
    if (fs.existsSync(dir) && !fs.readdirSync(dir).length) fs.rmdirSync(dir);
  }
  if (!opts.dryRun) fs.rmSync(path.join(opts.target, MANIFEST), { force: true });
  console.log(`${opts.dryRun ? "Would remove" : "Removed"} ${count(m.skills.length, "skill")} and ${count(m.agents.length, "agent")} from ${tilde(opts.target)}`);
}

const opts = parse(process.argv.slice(2));
const commands = { help, "--help": help, "-h": help, list, install, update: install, status, uninstall };
(commands[opts.command] || (() => fail(`unknown command "${opts.command}"; run "help"`)))(opts);
