import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('normalize', Path(__file__).parents[1] / 'signalroom-publish-normalize.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class VideoMeasurement(unittest.TestCase):
    def test_player_changes_preserve_identity_and_schema(self):
        src = '''<iframe src="https://www.youtube.com/embed/abc"></iframe>
<iframe src="https://www.youtube-nocookie.com/embed/def?autoplay=1&amp;playlist=def,ghi"></iframe>
player.src = `https://www.youtube-nocookie.com/embed/${videoId}?autoplay=1&playlist=${playlist}`;
{"embedUrl":"https://www.youtube.com/embed/abc"}
<a href="https://www.youtube.com/embed/abc">Video</a>'''
        out, count = mod.fix_video_api_in_html(src)
        self.assertEqual(count, 3)
        self.assertIn('embed/abc?enablejsapi=1', out)
        self.assertIn('playlist=def,ghi&amp;enablejsapi=1', out)
        self.assertIn('playlist=${playlist}&enablejsapi=1', out)
        self.assertIn('{"embedUrl":"https://www.youtube.com/embed/abc"}', out)
        self.assertIn('<a href="https://www.youtube.com/embed/abc">', out)
        self.assertEqual(mod.fix_video_api_in_html(out), (out, 0))

    def test_explicit_disabled_api_is_replaced(self):
        out, count = mod.fix_video_api_in_html('<iframe src="https://www.youtube.com/embed/abc?enablejsapi=0&amp;start=5">')
        self.assertEqual(count, 1)
        self.assertIn('enablejsapi=1&amp;start=5', out)
