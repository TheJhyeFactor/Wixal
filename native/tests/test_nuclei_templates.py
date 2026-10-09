import unittest
from wixal.nuclei_templates import validate

TEMPLATE=b'id: bounded\ninfo: {name: bounded, severity: info}\nhttp:\n  - method: GET\n    path: ["{{BaseURL}}"]\n    matchers: [{type: status, status: [200]}]\n'
class TemplateTests(unittest.TestCase):
    def test_selected_http_and_target_binding(self):
        self.assertEqual(validate(TEMPLATE),'bounded')
        for path in (b'https://other.example',b'{{BaseURL}}.other.example',b'{{RootURL}}/../x',b'{{BaseURL}}/{{random}}'):
            raw=TEMPLATE.replace(b'{{BaseURL}}',path)
            if path==b'{{RootURL}}/../x':self.assertEqual(validate(raw),'bounded')
            else:
                with self.assertRaises(ValueError):validate(raw)
    def test_code_raw_post_variables_aliases_and_duplicate_keys_are_rejected(self):
        for raw in (TEMPLATE+b'code: []\n',TEMPLATE+b'variables: {}\n',TEMPLATE.replace(b'GET',b'POST'),TEMPLATE.replace(b'path:',b'raw:'),TEMPLATE.replace(b'id: bounded',b'id: first\nid: bounded'),TEMPLATE.replace(b'info: {name: bounded, severity: info}',b'info: &a {name: bounded}\nother: *a')):
            with self.assertRaises(ValueError):validate(raw)
