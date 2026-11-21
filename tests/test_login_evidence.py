import json
import unittest
from app_core.login_evidence import capture,open_evidence


class LoginEvidenceTests(unittest.TestCase):
    def test_encrypted_response_redacts_password_and_codes_and_authenticates_flow(self):
        value={'password':'plain','verification_code':'123456','action':'echo plain #PWD_INSTAGRAM:4:123:YWJjZA==',
               'headers':{'authorization':'private-server-token'}}
        evidence=capture('flow',value,'plain',now=100)
        encoded=json.dumps(evidence)
        for secret in ('plain','123456','YWJjZA==','private-server-token'):
            self.assertNotIn(secret,encoded)
        restored=open_evidence('flow',evidence,now=101)
        self.assertEqual(restored['password'],'[redacted]')
        self.assertEqual(restored['verification_code'],'[redacted]')
        self.assertEqual(restored['action'],'echo [redacted] [redacted]')
        with self.assertRaises(ValueError):open_evidence('other-flow',evidence,now=101)
        with self.assertRaises(ValueError):open_evidence('flow',evidence,now=1001)

    def test_oversized_response_not_stored(self):
        self.assertEqual(capture('flow',{'data':'x'*2_000_001}),{'omitted':'response_too_large'})
