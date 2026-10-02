import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from action2plugin import convert  # noqa: E402

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "pause_on_large_transfer.js"


def test_signature_and_relayer_mapped():
    code, notes = convert(FIX.read_text(), "pauser", "pause-on-large-transfer")
    assert "export async function handler(context: PluginContext)" in code
    assert "api.useRelayer('pauser')" in code
    assert "client.sendTransaction(" in code
    assert "gas_limit:" in code
    assert "config.THRESHOLD" in code and "config.CONTRACT" in code
    assert "defender-sdk" not in code
    assert "'pause-on-large-transfer'" in code  # autotaskId replaced by plugin id
    assert any("handler signature" in n for n in notes)


def test_unmapped_items_become_todos():
    src = "const { DefenderRelayProvider } = require('defender-relay-client/lib/ethers');\nexports.handler = async function(event) { return 1; };"
    code, notes = convert(src, "r", "p")
    assert "TODO(action2plugin): Defender SDK import" in code
    assert "require('defender-relay-client" not in code
