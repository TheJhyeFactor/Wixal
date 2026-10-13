"""Theme compatibility at migration, account-preset and asset boundaries."""
import json
import re
import tempfile
import unittest
from pathlib import Path
from wixal.account import preferences
from wixal.migration import import_workspace
from wixal.preferences import THEMES, APP_ICONS, validate_ui
from wixal.storage import Store

ROOT=Path(__file__).resolve().parents[2]

class ThemeCatalogueTests(unittest.TestCase):
    def test_swift_engine_catalogues_and_shipped_icons_agree(self):
        swift=(ROOT/'native/Sources/ThemePalette.swift').read_text()
        names=re.findall(r'\.init\(name:"([^"]+)"',swift)
        self.assertEqual(tuple(n.lower() for n in names),THEMES)
        self.assertEqual(len(set(THEMES)),10)
        for icon in APP_ICONS:
            if icon=='theme':continue
            svg=(ROOT/f'assets/icon-variants/{icon}.svg').read_text()
            self.assertIn('viewBox="0 0 1024 1024"',svg)
            data=(ROOT/f'assets/icon-variants/{icon}.png').read_bytes()
            self.assertEqual(data[:8],b'\x89PNG\r\n\x1a\n')
            self.assertEqual(int.from_bytes(data[16:20],'big'),1024)
            self.assertEqual(int.from_bytes(data[20:24],'big'),1024)

    def test_all_themes_are_accepted_in_existing_account_presets(self):
        for theme in THEMES:
            value=dict(ui=dict(theme=theme,textSize=13,reduceMotion=False,sidebarCollapsed=False),contextSize=8192,mode='chat',autoSummary=True)
            self.assertEqual(preferences(value)['ui']['theme'],theme)

    def test_text_contrast_and_distinct_surface_layers(self):
        def luminance(hex_value):
            channels=[(hex_value>>shift&255)/255 for shift in (16,8,0)]
            linear=[c/12.92 if c<=0.04045 else ((c+0.055)/1.055)**2.4 for c in channels]
            return sum(c*w for c,w in zip(linear,(0.2126,0.7152,0.0722)))
        def contrast(a,b):
            low,high=sorted((luminance(a),luminance(b)))
            return (high+0.05)/(low+0.05)
        swift=(ROOT/'native/Sources/ThemePalette.swift').read_text()
        palettes=re.findall(r'\.init\(name:"(\w+)",(.*?)(?=\),?\n)',swift,re.S)
        self.assertEqual(len(palettes),10)
        self.assertEqual([name.lower() for name,body in palettes if 'light:true' in body],list(THEMES[:4]))
        for name,body in palettes:
            tokens={key:int(value,16) for key,value in re.findall(r'(\w+):0x([0-9A-F]+)',body)}
            with self.subTest(theme=name):
                self.assertEqual(len({tokens[k] for k in ('background','sidebar','panel','inset')}),4)
                for surface in ('background','sidebar','panel','raised','inset'):
                    for text in ('text','muted'):
                        self.assertGreaterEqual(contrast(tokens[text],tokens[surface]),4.5,(name,text,surface))
                for surface in ('background','sidebar','panel'):
                    self.assertGreaterEqual(contrast(tokens['accent'],tokens[surface]),4.5,(name,'accent',surface))

    def test_legacy_import_preserves_each_theme_and_independent_icon(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory)
            for theme in THEMES:
                with self.subTest(theme=theme):
                    store=Store(base/theme)
                    try:
                        source=base/(theme+'.json')
                        source.write_text(json.dumps(dict(projects=[],sessions=[],memories=[],ui=dict(theme=theme,appIcon='copper'))))
                        import_workspace(store,source)
                        self.assertEqual(store.data['ui']['theme'],theme)
                        self.assertEqual(store.data['ui']['appIcon'],'copper')
                    finally:store.close()

    def test_original_identifiers_still_work_and_bad_values_are_rejected(self):
        for theme in ('sakura','midnight','forest','paper'):
            self.assertEqual(validate_ui({'theme':theme})['theme'],theme)
        for patch in ({'theme':'Pearl'},{'theme':None},{'appIcon':None},{'theme':[]},{'textSize':True}):
            with self.assertRaises(ValueError):validate_ui(patch)
