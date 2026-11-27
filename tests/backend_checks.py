import sys, unittest, tempfile
from pathlib import Path
import numpy as np
import soundfile as sf
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"backend/v9"))
from audit_assets import audit
from request import normalize
class Checks(unittest.TestCase):
    def test_request(self):
        r=normalize(dict(job="Test01",instruments=["flute"],nature_layers={},seconds=60,engine="studio",format="flac"))
        self.assertEqual(r["seconds"],60)
        self.assertEqual(r["instruments"],["flute"])
        for patch in ({"seconds":0},{"instruments":["unknown"]},{"gains":{"flute":100}},{"seed":"bad seed"}):
            with self.assertRaises(ValueError):normalize({**r,**patch})
    def test_asset_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            sf.write(root/"fixture.wav",np.zeros((48000,2)),48000,subtype="PCM_24")
            # Synthetic test fixture only: not a real library asset or licence claim.
            record=dict(path="fixture.wav",title="Fixture",creator="Test",source_url="https://example.org/fixture",license="CC0-1.0",license_url="https://creativecommons.org/publicdomain/zero/1.0/",evidence="Unit test only",reviewed_by="Test",reviewed_on="2026-11-27",category="flute")
            out=audit(root,[record,record,{**record,"license":"CC-BY-NC-4.0"},{**record,"path":"../missing.wav"}])
            self.assertEqual(out["accepted_count"],1)
            self.assertEqual(out["rejected_count"],3)
    def test_pcm24_prefix(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"test.flac"
            x=np.random.default_rng(42).integers(-8388608,8388608,(48000,2),dtype=np.int32)<<8
            sf.write(p,x,48000,subtype="PCM_24")
            y,sr=sf.read(p,dtype="int32",always_2d=True)
            self.assertEqual(sr,48000)
            np.testing.assert_array_equal(x,y)
if __name__=="__main__":unittest.main()
