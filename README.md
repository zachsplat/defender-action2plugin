# defender-action2plugin

Scaffold an OpenZeppelin Relayer plugin from a Defender Action (Autotask).

OpenZeppelin Defender was retired on 2026-07-01. Its migration guide exported Monitors and Relayers as OpenZeppelin Monitor and Relayer configs, but custom Actions were not migrated: "you will need to manually recreate any custom action logic". This tool does the mechanical part of that recreation and leaves clearly marked TODOs for the rest.

It is a scaffolder, not a transpiler. Read the output before you deploy it.

## Usage

```bash
python3 action2plugin.py my-action.js --relayer my-relayer --id my-action
# writes my-action.plugin.ts and prints the plugins[] entry for config/config.json
```

No dependencies beyond Python 3.10+. Tests: `python3 -m pytest tests`.

## What it maps

| Defender Action | Relayer plugin |
|---|---|
| `exports.handler = async function(event)` | `export async function handler(context: PluginContext)` |
| `const { request, secrets } = event` | `params`, `headers` and `config` from `context` |
| `event.request.body`, `event.request.params` | `context.params` |
| `event.request.headers` | `context.headers` |
| `event.secrets.X`, `secrets.X` | `context.config.X` (declare under `plugins[].config`, or read from the relayer's environment) |
| `new Defender(event)`, `new Relayer(...)` | `context.api.useRelayer('<relayer id>')` |
| `client.relaySigner.sendTransaction({...})` | `relayer.sendTransaction({...})` |
| `gasLimit:`, `validUntil:` | `gas_limit:`, `valid_until:` |
| `new KeyValueStoreClient(event)` | `context.kv` |
| `event.autotaskId` | the plugin id |
| `require('@openzeppelin/defender-sdk')` and friends | removed |

## What it flags as TODO

Defender relay providers and signers for reads (use your own `ethers.JsonRpcProvider`; writes go through `relayer.sendTransaction`), `relaySigner.sign` / `signTypedData`, Action and Workflow chaining, `process.env`, `autotaskRunId`, and any `event.request.*` field it does not recognise.

## Example

`fixtures/pause_on_large_transfer.js` is a typical Action: on a monitor match above a threshold, call `pause()` through the relayer. `fixtures/pause_on_large_transfer.plugin.ts` is the generated output.

## Reference

OpenZeppelin Relayer plugins: https://docs.openzeppelin.com/relayer/plugins
Defender migration guide: https://docs.openzeppelin.com/defender/migration

## License

MIT.
