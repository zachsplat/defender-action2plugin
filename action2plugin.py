#!/usr/bin/env python3
"""Defender Action (Autotask) to OpenZeppelin Relayer plugin scaffolder.

Defender was retired on 2026-07-01 and its migration guide says custom Actions are not migrated. This tool
takes an Action's JavaScript/TypeScript source and produces a Relayer plugin skeleton with the mappings that
are mechanical applied, and a TODO list for everything that is not. It is a scaffolder, not a transpiler:
the output must be read before it is deployed.

Mappings applied:
  exports.handler = async function(event)        -> export async function handler(context: PluginContext)
  const { request, secrets } = event              -> const params = context.params; const secrets = context.config
  event.request.body / event.request.params      -> context.params
  event.secrets.X / secrets.X                    -> context.config.X   (declare under plugins[].config or env)
  new Defender(event) / new Relayer(...)         -> const relayer = context.api.useRelayer('<RELAYER_ID>')
  relayer.sendTransaction({...})                 -> relayer.sendTransaction({...})  (field names differ: gasLimit -> gas_limit, speed -> speed)
  client.relaySigner.sendTransaction({...})      -> relayer.sendTransaction({...})
  autotaskId / autotaskRunId                     -> TODO: no equivalent; use plugin id and context.kv
  KeyValueStoreClient                            -> context.kv (get/set/del)
  event.request.headers                          -> context.headers
  ethers provider from DefenderRelayProvider     -> TODO: use an RPC provider of your own (ethers.JsonRpcProvider) for reads; writes go through relayer.sendTransaction

Usage: action2plugin.py action.js [--relayer my-relayer] [--out plugin.ts]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

TODO = "// TODO(action2plugin): "

RULES: list[tuple[str, str, str]] = [
    # (regex, replacement, note)
    (r"exports\.handler\s*=\s*async\s*(?:function)?\s*\(\s*(\w+)\s*\)\s*(?:=>)?\s*\{",
     "export async function handler(context: PluginContext) {\n  const { api, params, kv, headers, config } = context;",
     "handler signature mapped"),
    (r"module\.exports\s*=\s*\{\s*handler\s*\}\s*;?", "", "module.exports removed (ESM export used)"),
    (r"const\s*\{\s*([^}]*)\}\s*=\s*event\s*;", lambda m: _destructure(m.group(1)), "event destructuring mapped"),
    (r"event\.request\.body", "params", "event.request.body -> context.params"),
    (r"event\.request\.params", "params", "event.request.params -> context.params"),
    (r"event\.request\.headers", "headers", "event.request.headers -> context.headers"),
    (r"event\.secrets\.(\w+)", r"config.\1", "event.secrets.X -> context.config.X"),
    (r"\bsecrets\.(\w+)", r"config.\1", "secrets.X -> context.config.X"),
    (r"new\s+Defender\s*\(\s*\w+\s*\)", "api.useRelayer('__RELAYER_ID__')", "Defender client -> context.api.useRelayer"),
    (r"new\s+Relayer\s*\(\s*\w+\s*\)", "api.useRelayer('__RELAYER_ID__')", "Relayer client -> context.api.useRelayer"),
    (r"(\w+)\.relaySigner\.sendTransaction\(", r"\1.sendTransaction(", "relaySigner.sendTransaction -> relayer.sendTransaction"),
    (r"\bgasLimit\s*:", "gas_limit:", "gasLimit -> gas_limit"),
    (r"\bvalidUntil\s*:", "valid_until:", "validUntil -> valid_until"),
    (r"new\s+KeyValueStoreClient\s*\(\s*\w+\s*\)", "kv", "KeyValueStoreClient -> context.kv"),
    (r"event\.autotaskId", "'__PLUGIN_ID__'", "autotaskId -> plugin id"),
    (r"event\.autotaskRunId", "undefined /* no run id */", "autotaskRunId has no equivalent"),
]

UNMAPPED = [
    (r"DefenderRelayProvider|DefenderRelaySigner|defender-relay-client|@openzeppelin/defender-sdk", "Defender SDK import: replace reads with your own ethers.JsonRpcProvider and writes with relayer.sendTransaction"),
    (r"require\(\s*['\"]axios['\"]\s*\)|from\s+['\"]axios['\"]", "axios: allowed, add to plugins/package.json"),
    (r"event\.request\.", "other event.request.* fields: check context"),
    (r"relaySigner\.signTypedData|relaySigner\.sign\(", "signing arbitrary messages: use relayer.sign / signTypedData in relayer-sdk, check support for your signer type"),
    (r"actionId|workflow", "Workflow/Action chaining: no equivalent; call other plugins via HTTP or merge"),
    (r"process\.env\.", "process.env: set these in the relayer container environment"),
]


def _destructure(inner: str) -> str:
    names = [n.strip() for n in inner.split(",") if n.strip()]
    out = []
    for n in names:
        base = n.split(":")[0].strip()
        if base == "request":
            out.append("const request = { body: params, params, headers };")
        elif base == "secrets":
            out.append("const secrets = config;")
        elif base in ("autotaskId", "autotaskRunId"):
            out.append(f"{TODO}{base} has no Relayer equivalent")
        else:
            out.append(f"{TODO}event.{base} not mapped")
    return "\n  ".join(out)


def convert(src: str, relayer_id: str, plugin_id: str) -> tuple[str, list[str]]:
    notes: list[str] = []
    out = src
    for pattern, repl, note in RULES:
        new = re.sub(pattern, repl, out)
        if new != out:
            notes.append(note)
            out = new
    out = out.replace("__RELAYER_ID__", relayer_id).replace("__PLUGIN_ID__", plugin_id)
    todos = []
    for pattern, msg in UNMAPPED:
        if re.search(pattern, out):
            todos.append(msg)
    header = (
        "import { PluginContext, pluginError, Speed } from '@openzeppelin/relayer-sdk';\n"
        f"{TODO}generated from a Defender Action; review every line before deploying\n"
        + "".join(f"{TODO}{t}\n" for t in todos)
        + "\n"
    )
    # strip old requires of defender packages
    out = re.sub(r"^.*require\(\s*['\"](?:defender-|@openzeppelin/defender)[^'\"]*['\"]\s*\).*$\n?", "", out, flags=re.M)
    out = re.sub(r"^import .* from ['\"](?:defender-|@openzeppelin/defender)[^'\"]*['\"];?\s*$\n?", "", out, flags=re.M)
    return header + out, notes + [f"TODO: {t}" for t in todos]


def plugin_config(plugin_id: str, path: str) -> dict:
    return {"id": plugin_id, "path": path, "timeout": 60, "emit_logs": True, "config": {}}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("action", type=Path)
    ap.add_argument("--relayer", default="my-relayer")
    ap.add_argument("--id", default=None)
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args(argv)
    src = a.action.read_text()
    pid = a.id or re.sub(r"[^a-z0-9-]", "-", a.action.stem.lower())
    code, notes = convert(src, a.relayer, pid)
    out = a.out or a.action.with_suffix(".plugin.ts")
    out.write_text(code)
    print(f"wrote {out}")
    print("applied:")
    for n in notes:
        print("  -", n)
    print("\nadd to config/config.json plugins[]:")
    import json
    print(json.dumps(plugin_config(pid, out.name), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
