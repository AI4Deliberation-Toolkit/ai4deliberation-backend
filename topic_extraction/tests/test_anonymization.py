from django.test import TestCase

from topic_extraction.anonymization import scrub_text


class ScrubEmailTest(TestCase):
    def test_replaces_simple_email(self):
        result = scrub_text('Επικοινωνία: user@example.gr για ερωτήσεις')
        self.assertNotIn('user@example.gr', result)
        self.assertIn('[EMAIL]', result)

    def test_replaces_multiple_emails(self):
        result = scrub_text('a@b.com and c@d.org')
        self.assertEqual(result.count('[EMAIL]'), 2)
        self.assertNotIn('@', result)

    def test_handles_email_with_plus_and_dots(self):
        result = scrub_text('first.last+tag@subdomain.example.gr')
        self.assertNotIn('first.last', result)
        self.assertIn('[EMAIL]', result)


class ScrubPhoneTest(TestCase):
    def test_replaces_greek_mobile_with_country_code(self):
        result = scrub_text('Τηλέφωνο: +30 6912345678')
        self.assertNotIn('6912345678', result)
        self.assertIn('[PHONE]', result)

    def test_replaces_greek_landline_ten_digits(self):
        result = scrub_text('Καλέστε 2101234567 σήμερα')
        self.assertNotIn('2101234567', result)
        self.assertIn('[PHONE]', result)

    def test_replaces_greek_mobile_ten_digits(self):
        result = scrub_text('Επικοινωνία 6987654321')
        self.assertNotIn('6987654321', result)
        self.assertIn('[PHONE]', result)

    def test_does_not_replace_random_nine_digit_number(self):
        # Years, postal codes, plain numbers should not get scrubbed as phones
        result = scrub_text('Το έτος 2024 και κωδικός 12345')
        self.assertNotIn('[PHONE]', result)
        self.assertIn('2024', result)
        self.assertIn('12345', result)


class ScrubAfmTest(TestCase):
    def test_replaces_afm_with_prefix(self):
        result = scrub_text('ΑΦΜ: 123456789 της εταιρείας')
        self.assertNotIn('123456789', result)
        self.assertIn('[AFM]', result)

    def test_replaces_afm_lowercase_prefix(self):
        result = scrub_text('αφμ 987654321')
        self.assertNotIn('987654321', result)
        self.assertIn('[AFM]', result)

    def test_does_not_replace_bare_nine_digit_number(self):
        # Without ΑΦΜ context, a 9-digit number is ambiguous; leave it.
        result = scrub_text('Αριθμός 123456789 σε άλλο πλαίσιο')
        self.assertNotIn('[AFM]', result)
        self.assertIn('123456789', result)


class ScrubIbanTest(TestCase):
    def test_replaces_greek_iban(self):
        # Greek IBAN format: GR + 2 digits + 23 alphanumeric (27 total)
        result = scrub_text('Λογαριασμός: GR1601101250000000012300695')
        self.assertNotIn('GR1601101250000000012300695', result)
        self.assertIn('[IBAN]', result)

    def test_replaces_iban_with_spaces(self):
        result = scrub_text('IBAN: GR16 0110 1250 0000 0001 2300 695')
        self.assertIn('[IBAN]', result)
        self.assertNotIn('0110 1250', result)

    def test_does_not_replace_random_alphanumeric(self):
        result = scrub_text('Κωδικός ABC123XYZ απλός')
        self.assertNotIn('[IBAN]', result)
        self.assertIn('ABC123XYZ', result)


class ScrubCombinedTest(TestCase):
    def test_handles_text_with_multiple_pii_types(self):
        text = (
            'Επικοινωνία: user@example.gr, τηλ. +30 6912345678, '
            'ΑΦΜ 123456789, IBAN GR1601101250000000012300695'
        )
        result = scrub_text(text)
        self.assertIn('[EMAIL]', result)
        self.assertIn('[PHONE]', result)
        self.assertIn('[AFM]', result)
        self.assertIn('[IBAN]', result)
        self.assertNotIn('user@example.gr', result)
        self.assertNotIn('6912345678', result)
        self.assertNotIn('123456789', result)
        self.assertNotIn('GR1601101250000000012300695', result)

    def test_leaves_plain_legislative_text_unchanged(self):
        text = (
            'Το παρόν άρθρο ρυθμίζει τα δικαιώματα των πολιτών '
            'στη συμμετοχή σε διαβουλεύσεις.'
        )
        result = scrub_text(text)
        self.assertEqual(result, text)

    def test_empty_string_returns_empty(self):
        self.assertEqual(scrub_text(''), '')

    def test_none_raises_type_error(self):
        with self.assertRaises((TypeError, AttributeError)):
            scrub_text(None)
