const { Defender } = require('@openzeppelin/defender-sdk');
const { ethers } = require('ethers');

const ABI = ['function pause()'];

exports.handler = async function (event) {
  const { request, secrets } = event;
  const payload = request.body;
  const threshold = secrets.THRESHOLD || '1000000000';
  const match = payload.events && payload.events[0];
  if (!match) {
    return { skipped: true };
  }
  const amount = match.matchReasons[0].params.value;
  if (BigInt(amount) < BigInt(threshold)) {
    return { skipped: true, amount };
  }
  const client = new Defender(event);
  const iface = new ethers.Interface(ABI);
  const data = iface.encodeFunctionData('pause', []);
  const tx = await client.relaySigner.sendTransaction({
    to: secrets.CONTRACT,
    data,
    gasLimit: 100000,
    speed: 'fast',
  });
  return { paused: true, hash: tx.hash, autotask: event.autotaskId };
};
