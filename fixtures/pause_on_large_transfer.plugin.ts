import { PluginContext, pluginError, Speed } from '@openzeppelin/relayer-sdk';
// TODO(action2plugin): generated from a Defender Action; review every line before deploying
// TODO(action2plugin): Defender SDK import: replace reads with your own ethers.JsonRpcProvider and writes with relayer.sendTransaction

const { ethers } = require('ethers');

const ABI = ['function pause()'];

export async function handler(context: PluginContext) {
  const { api, params, kv, headers, config } = context;
  const request = { body: params, params, headers };
  const secrets = config;
  const payload = request.body;
  const threshold = config.THRESHOLD || '1000000000';
  const match = payload.events && payload.events[0];
  if (!match) {
    return { skipped: true };
  }
  const amount = match.matchReasons[0].params.value;
  if (BigInt(amount) < BigInt(threshold)) {
    return { skipped: true, amount };
  }
  const client = api.useRelayer('my-relayer');
  const iface = new ethers.Interface(ABI);
  const data = iface.encodeFunctionData('pause', []);
  const tx = await client.sendTransaction({
    to: config.CONTRACT,
    data,
    gas_limit: 100000,
    speed: 'fast',
  });
  return { paused: true, hash: tx.hash, autotask: 'pause-on-large-transfer' };
};
