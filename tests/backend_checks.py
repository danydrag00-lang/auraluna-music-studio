import sys, unittest, tempfile
from pathlib import Path
import numpy as np
import soundfile as sf
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"backend/v9"))
from audit_assets import audit
from request import normalize
from join_parts import smooth_filter, smooth_join
import subprocess, shutil, json
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
    def test_smooth_join_graph(self):
        graph,last=smooth_filter(12,12)
        self.assertEqual(graph.count("acrossfade=d=12:c1=tri:c2=tri"),11)
        self.assertEqual(last,"[mix11]")
        with self.assertRaises(ValueError):smooth_filter(13)
    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),"FFmpeg unavailable")
    def test_actual_transition_render(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            sr=48000
            seconds=6
            time=np.arange(sr*seconds)/sr
            paths=[]
            for i,freq in enumerate((220,330,440)):
                wave=.12*np.sin(2*np.pi*freq*time)
                path=root/f"part{i}.wav"
                sf.write(path,np.column_stack((wave,wave)),sr,subtype="PCM_24")
                paths.append(path)
            for fmt,rate in (("m4a","256k"),("mp3","320k")):
                out=root/("mix."+fmt)
                smooth_join(paths,out,fmt,rate,2)
                decoded=subprocess.check_output(["ffmpeg","-v","error","-i",str(out),"-f","f32le","-acodec","pcm_f32le","-"])
                samples=np.frombuffer(decoded,dtype="<f4").reshape(-1,2)
                self.assertLess(abs(len(samples)/sr-14),.1)
                self.assertTrue(np.isfinite(samples).all())
                self.assertLess(np.max(np.abs(samples)),.85)
                for center in (5,9):
                    part=samples[int((center-.5)*sr):int((center+.5)*sr)]
                    self.assertGreater(np.sqrt(np.mean(part**2)),.025)
                print("Transition fixture",fmt,"seconds",len(samples)/sr,"peak",float(np.max(np.abs(samples))))
    def test_pcm24_prefix(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"test.flac"
            x=np.random.default_rng(42).integers(-8388608,8388608,(48000,2),dtype=np.int32)<<8
            sf.write(p,x,48000,subtype="PCM_24")
            y,sr=sf.read(p,dtype="int32",always_2d=True)
            self.assertEqual(sr,48000)
            np.testing.assert_array_equal(x,y)
if __name__=="__main__":unittest.main()
