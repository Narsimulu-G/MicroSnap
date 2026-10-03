import io
import json
import os
import unittest
from unittest.mock import Mock, patch
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PIL import Image
from google.genai import types
from core import normalize_phone, prepare_image, clean_summary, friendly_error
from services import generate_reply, generate_summary, make_content, send_whatsapp
from streamlit.testing.v1 import AppTest


class ValidationTests(unittest.TestCase):
    def test_phone(self):
        self.assertEqual(normalize_phone('+91 (98765) 43210'), '+919876543210')
        for invalid in ['9876543210', '+01234', '+91abc', '']:
            with self.assertRaises(ValueError):
                normalize_phone(invalid)

    def test_photo(self):
        data = io.BytesIO()
        Image.new('RGB', (1800, 900), 'green').save(data, format='PNG')
        result, mime = prepare_image(data.getvalue())
        self.assertEqual(mime, 'image/jpeg')
        self.assertEqual(Image.open(io.BytesIO(result)).size, (1600, 800))
        for bad in [b'not an image', b'x' * (5 * 1024 * 1024 + 1)]:
            with self.assertRaises(ValueError):
                prepare_image(bad)

    def test_summary_no_silent_truncation(self):
        self.assertEqual(clean_summary('hello\n world'), 'hello world')
        for text in ['', 'x' * 1501]:
            with self.assertRaises(ValueError):
                clean_summary(text)

    def test_error_does_not_expose_raw_details(self):
        self.assertNotIn('secret-token', friendly_error(Exception('secret-token')))


class ServiceTests(unittest.TestCase):
    def test_summary_does_not_mutate_history(self):
        client = Mock()
        client.models.generate_content.return_value.text = 'Meal: approximately 400 kcal.'
        history = [make_content('Lunch')]
        before = list(history)
        self.assertIn('400', generate_summary(client, 'test-model', history))
        self.assertEqual(history, before)

    def test_reply_preserves_model_content_and_history(self):
        client = Mock()
        answer = types.Content(role='model', parts=[types.Part.from_text(text='Estimate')])
        client.models.generate_content.return_value = Mock(text='Estimate', candidates=[Mock(content=answer)])
        history = []
        text, returned = generate_reply(client, 'test-model', history, make_content('Rice'))
        self.assertEqual(text, 'Estimate')
        self.assertIs(returned, answer)
        self.assertEqual(history, [])
        client.models.generate_content.side_effect = RuntimeError('API down')
        with self.assertRaises(RuntimeError):
            generate_reply(client, 'test-model', history, make_content('Rice'))
        self.assertEqual(history, [])

    def test_session_send(self):
        client = Mock()
        send_whatsapp(client, 'whatsapp:+14155238886', '+919876543210', 'Test', 'Meal 400 kcal')
        kwargs = client.messages.create.call_args.kwargs
        self.assertEqual(kwargs['to'], 'whatsapp:+919876543210')
        self.assertIn('Meal 400 kcal', kwargs['body'])
        self.assertNotIn('content_sid', kwargs)

    def test_template_send(self):
        client = Mock()
        send_whatsapp(client, '+14155238886', '+919876543210', 'Test', 'Meal 400 kcal', 'template', 'HX123')
        kwargs = client.messages.create.call_args.kwargs
        self.assertEqual(json.loads(kwargs['content_variables']), {'1': 'Test', '2': 'Meal 400 kcal'})
        self.assertNotIn('body', kwargs)

    def test_failed_generation_cannot_send(self):
        client = Mock()
        with self.assertRaises(ValueError):
            send_whatsapp(client, '+14155238886', '+919876543210', 'Test', '')
        client.messages.create.assert_not_called()


class UITests(unittest.TestCase):
    def app(self):
        return AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'), default_timeout=15)

    @patch.dict(os.environ, {'GEMINI_API_KEY': ''})
    def test_missing_key(self):
        at = self.app().run()
        self.assertEqual(len(at.exception), 0)
        self.assertIn('Add your Gemini', at.info[0].value)

    @patch('google.genai.Client', return_value=Mock())
    @patch.dict(os.environ, {'GEMINI_API_KEY': 'test-not-real'})
    def test_onboard_and_summary_without_live_calls(self, mock_client):
        at = self.app().run()
        self.assertEqual(len(at.exception), 0)
        at.text_input[0].set_value('Test User')
        at.text_input[1].set_value('+919876543210')
        at.checkbox[0].check()
        at.button[0].click().run()
        self.assertEqual(len(at.exception), 0)
        self.assertEqual(at.session_state.profile['name'], 'Test User')
        model_content = types.Content(role='model', parts=[types.Part.from_text(text='Approximately 400 kcal')])
        with patch('services.generate_reply', return_value=('Approximately 400 kcal', model_content)):
            at.chat_input[0].set_value('A bowl of rice').run()
        self.assertEqual(len(at.exception), 0)
        self.assertEqual(len(at.session_state.history), 2)
        with patch('services.generate_summary', return_value='Rice: approximately 400 kcal.'):
            next(b for b in at.button if b.label == 'Generate summary').click().run()
        self.assertEqual(len(at.exception), 0)
        self.assertIn('400', at.session_state.summary)
        next(b for b in at.button if b.label == 'Start a new conversation').click().run()
        self.assertEqual(at.session_state.history, [])
        self.assertEqual(at.session_state.summary, '')


if __name__ == '__main__':
    unittest.main()
