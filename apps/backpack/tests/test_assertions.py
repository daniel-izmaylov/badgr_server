import base64
import collections
import dateutil.parser
import json
from openbadges.verifier.openbadges_context import (OPENBADGES_CONTEXT_V2_URI, OPENBADGES_CONTEXT_V1_URI,
                                                    OPENBADGES_CONTEXT_V2_DICT)
from openbadges_bakery import bake, unbake
import os
import responses
from issuer.utils import generate_sha256_hashstring

from django.urls import reverse

from badgeuser.models import CachedEmailAddress
from issuer.models import BadgeClass, Issuer, BadgeInstance
from mainsite.tests.base import BadgrTestCase, SetupIssuerHelper
from mainsite.utils import first_node_match, OriginSetting

from backpack.models import BackpackCollection, BackpackCollectionBadgeInstance
from backpack.serializers_v1 import (CollectionSerializerV1)

from .utils import setup_basic_0_5_0, setup_basic_1_0, setup_resources, CURRENT_DIRECTORY


class TestBadgeUploads(BadgrTestCase):
    @responses.activate
    def test_submit_basic_1_0_badge_via_url(self):
        setup_basic_1_0()
        setup_resources([
            {'url': OPENBADGES_CONTEXT_V1_URI, 'filename': 'v1_context.json'},
            {'url': OPENBADGES_CONTEXT_V2_URI, 'response_body': json.dumps(OPENBADGES_CONTEXT_V2_DICT)}
        ])
        self.setup_user(email='test@example.com', token_scope='rw:backpack')

        post_input = {
            'url': 'http://a.com/instance'
        }
        response = self.client.post(
            '/v1/earner/badges', post_input
        )
        self.assertEqual(response.status_code, 201)
        get_response = self.client.get('/v1/earner/badges')
        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(
            get_response.data[0].get('json', {}).get('id'), 'http://a.com/instance',
            "The badge in our backpack should report its JSON-LD id as its original OpenBadgeId"
        )

        new_instance = BadgeInstance.objects.first()
        expected_url = "{}{}".format(OriginSetting.HTTP, reverse('badgeinstance_image', kwargs=dict(entity_id=new_instance.entity_id)))
        self.assertEqual(get_response.data[0].get('json', {}).get('image', {}).get('id'), expected_url)

    @responses.activate
    def test_submit_basic_1_1_badge_via_url(self):
        assertion_data = {
            '@context': 'https://w3id.org/openbadges/v1',
            'id': 'http://a.com/instance',
            'type': 'Assertion',
            "recipient": {"identity": "test@example.com", "hashed": False, "type": "email"},
            "badge": "http://a.com/badgeclass",
            "issuedOn": "2015-04-30",
            "verify": {"type": "hosted", "url": "http://a.com/instance"}
        }
        badgeclass_data = {
            '@context': 'https://w3id.org/openbadges/v1',
            'type': 'BadgeClass',
            'id': 'http://a.com/badgeclass',
            "name": "Basic Badge",
            "description": "Basic as it gets. v1.0",
            "image": "http://a.com/badgeclass_image",
            "criteria": "http://a.com/badgeclass_criteria",
            "issuer": "http://a.com/issuer"
        }
        issuer_data = {
            '@context': 'https://w3id.org/openbadges/v1',
            'type': 'Issuer',
            'id': 'http://a.com/issuer',
            "name": "Basic Issuer",
            "url": "http://a.com/issuer/website"
        }
        for d in [assertion_data, badgeclass_data, issuer_data]:
            responses.add(
                responses.GET, d['id'], json=d
            )

        responses.add(
            responses.GET, 'http://a.com/badgeclass_image',
            body=open(os.path.join(CURRENT_DIRECTORY, 'testfiles/unbaked_image.png')).read(),
            status=200, content_type='image/png'
        )

        setup_resources([
            {'url': OPENBADGES_CONTEXT_V1_URI, 'filename': 'v1_context.json'},
            {'url': OPENBADGES_CONTEXT_V2_URI, 'response_body': json.dumps(OPENBADGES_CONTEXT_V2_DICT)}
        ])

        self.setup_user(email='test@example.com', token_scope='rw:backpack')

        post_input = {
            'url': 'http://a.com/instance'
        }
        response = self.client.post(
            '/v1/earner/badges', post_input
        )
        self.assertEqual(response.status_code, 201)
        get_response = self.client.get('/v1/earner/badges')
        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(
            get_response.data[0].get('json', {}).get('id'), 'http://a.com/instance',
            "The badge in our backpack should report its JSON-LD id as its original OpenBadgeId"
        )

        new_instance = BadgeInstance.objects.first()
        expected_url = "{}{}".format(OriginSetting.HTTP, reverse('badgeinstance_image', kwargs=dict(entity_id=new_instance.entity_id)))
        self.assertEqual(get_response.data[0].get('json', {}).get('image', {}).get('id'), expected_url)

    @responses.activate
    def test_submit_basic_1_0_badge_via_url_plain_json(self):
        setup_basic_1_0()
        self.setup_user(email='test@example.com', token_scope='rw:backpack')
        setup_resources([
            {'url': OPENBADGES_CONTEXT_V1_URI, 'filename': 'v1_context.json'},
            {'url': OPENBADGES_CONTEXT_V2_URI, 'response_body': json.dumps(OPENBADGES_CONTEXT_V2_DICT)}
        ])

        post_input = {
            'url': 'http://a.com/instance'
        }
        response = self.client.post(
            '/v1/earner/badges?json_format=plain', post_input
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            response.data.get('json').get('badge').get('description'),
            u'Basic as it gets. v1.0'
        )

    @responses.activate
    def test_submit_basic_1_0_badge_via_url_bad_email(self):
        setup_basic_1_0()
        setup_resources([
            {'url': OPENBADGES_CONTEXT_V1_URI, 'filename': 'v1_context.json'},
            {'url': OPENBADGES_CONTEXT_V2_URI, 'response_body': json.dumps(OPENBADGES_CONTEXT_V2_DICT)}
        ])
        self.setup_user(email='not.test@email.example.com', authenticate=True)

        post_input = {
            'url': 'http://a.com/instance'
        }
        response = self.client.post(
            '/v1/earner/badges', post_input
        )
        self.assertEqual(response.status_code, 400)
        self.assertIsNotNone(first_node_match(response.data, dict(
            messageLevel='ERROR',
            name='VERIFY_RECIPIENT_IDENTIFIER',
        )))

    @responses.activate
    def test_submit_basic_1_0_badge_from_image_url_baked_w_assertion(self):
        setup_basic_1_0()
        self.setup_user(email='test@example.com', authenticate=True)
        setup_resources([
            {'url': OPENBADGES_CONTEXT_V1_URI, 'filename': 'v1_context.json'},
            {'url': OPENBADGES_CONTEXT_V2_URI, 'response_body': json.dumps(OPENBADGES_CONTEXT_V2_DICT)}
        ])

        responses.add(
            responses.GET, 'http://a.com/baked_image',
            body=open(os.path.join(CURRENT_DIRECTORY, 'testfiles/baked_image.png')).read(),
            status=200, content_type='image/png'
        )

        post_input = {
            'url': 'http://a.com/baked_image'
        }
        response = self.client.post(
            '/v1/earner/badges', post_input
        )
        self.assertEqual(response.status_code, 201)
        get_response = self.client.get('/v1/earner/badges')
        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(
            get_response.data[0].get('json', {}).get('id'), 'http://a.com/instance',
            "The badge in our backpack should report its JSON-LD id as its original OpenBadgeId"
        )


    @responses.activate
    def test_submit_basic_1_0_badge_image_png(self):
        setup_basic_1_0()
        setup_resources([
            {'url': OPENBADGES_CONTEXT_V1_URI, 'filename': 'v1_context.json'},
            {'url': OPENBADGES_CONTEXT_V2_URI, 'response_body': json.dumps(OPENBADGES_CONTEXT_V2_DICT)}
        ])
        self.setup_user(email='test@example.com', authenticate=True)

        image = open(os.path.join(CURRENT_DIRECTORY, 'testfiles/baked_image.png'))
        post_input = {
            'image': image
        }
        response = self.client.post(
            '/v1/earner/badges', post_input
        )
        self.assertEqual(response.status_code, 201)
        get_response = self.client.get('/v1/earner/badges')
        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(
            get_response.data[0].get('json', {}).get('id'), 'http://a.com/instance',
            "The badge in our backpack should report its JSON-LD id as its original OpenBadgeId"
        )

    @responses.activate
    def test_submit_baked_1_1_badge_preserves_metadata_roundtrip(self):
        assertion_metadata = {
            "@context": "https://w3id.org/openbadges/v1",
            "type": "Assertion",
            "id": "http://a.com/instance2",
            "recipient": {"identity": "test@example.com", "hashed": False, "type": "email"},
            "badge": "http://a.com/badgeclass",
            "issuedOn": "2015-04-30T00:00+00:00",
            "verify": {"type": "hosted", "url": "http://a.com/instance2"},
            "extensions:ExampleExtension": {
                "@context": "https://openbadgespec.org/extensions/exampleExtension/context.json",
                "type": ["Extension", "extensions:ExampleExtension"],
                "exampleProperty": "some extended text"
            },
            "schema:unknownMetadata": 55
        }
        badgeclass_metadata = {
            "@context": "https://w3id.org/openbadges/v1",
            "type": "BadgeClass",
            "id": "http://a.com/badgeclass",
            "name": "Basic Badge",
            "description": "Basic as it gets. v1.1",
            "image": "http://a.com/badgeclass_image",
            "criteria": "http://a.com/badgeclass_criteria",
            "issuer": "http://a.com/issuer"
        }
        issuer_metadata = {
            "@context": "https://w3id.org/openbadges/v1",
            "type": "Issuer",
            "id": "http://a.com/issuer",
            "name": "Basic Issuer",
            "url": "http://a.com/issuer/website"
        }

        with open(os.path.join(CURRENT_DIRECTORY, 'testfiles/baked_image.png')) as image_file:
            original_image = bake(image_file, json.dumps(assertion_metadata))
            original_image.seek(0)

        responses.add(
            responses.GET, 'http://a.com/badgeclass_image',
            body=open(os.path.join(CURRENT_DIRECTORY, 'testfiles/unbaked_image.png')).read(),
            status=200, content_type='image/png'
        )

        setup_resources([
            {'url': OPENBADGES_CONTEXT_V1_URI, 'filename': 'v1_context.json'},
            {'url': OPENBADGES_CONTEXT_V2_URI, 'response_body': json.dumps(OPENBADGES_CONTEXT_V2_DICT)},
            {'url': "https://openbadgespec.org/extensions/exampleExtension/context.json", 'response_body': json.dumps(
                {
                    "@context": {
                        "obi": "https://w3id.org/openbadges#",
                        "extensions": "https://w3id.org/openbadges/extensions#",
                        "exampleProperty": "http://schema.org/text"
                    },
                    "obi:validation": [
                        {
                            "obi:validatesType": "extensions:ExampleExtension",
                            "obi:validationSchema": "https://openbadgespec.org/extensions/exampleExtension/schema.json"
                        }
                    ]
                }
            )},
            {'url': "https://openbadgespec.org/extensions/exampleExtension/schema.json", 'response_body': json.dumps(
                {
                    "$schema": "http://json-schema.org/draft-04/schema#",
                    "title": "1.1 Open Badge Example Extension",
                    "description": "An extension that allows you to add a single string exampleProperty to an extension object to represent some of your favorite text.",
                    "type": "object",
                    "properties": {
                        "exampleProperty": {
                            "type": "string"
                        }
                    },
                    "required": [
                        "exampleProperty"
                    ]
                }
            )},
            {'url': 'http://a.com/instance2', 'response_body': json.dumps(assertion_metadata)},
            {'url': 'http://a.com/badgeclass', 'response_body': json.dumps(badgeclass_metadata)},
            {'url': 'http://a.com/issuer', 'response_body': json.dumps(issuer_metadata)}
        ])
        self.setup_user(email='test@example.com', authenticate=True)

        self.assertDictEqual(json.loads(unbake(original_image)), assertion_metadata)

        original_image.seek(0)
        response = self.client.post('/v1/earner/badges', {'image': original_image})
        self.assertEqual(response.status_code, 201)

        public_url = response.data.get('shareUrl')
        self.assertIsNotNone(public_url)
        response = self.client.get(public_url, Accept="application/json")

        for key in ['issuedOn']:
            fetched_ts = dateutil.parser.parse(response.data.get(key))
            metadata_ts = dateutil.parser.parse(assertion_metadata.get(key))
            self.assertEqual(fetched_ts, metadata_ts)

        for key in ['recipient', 'extensions:ExampleExtension']:
            fetched_dict = response.data.get(key)
            self.assertIsNotNone(fetched_dict, "Field '{}' is missing".format(key))
            metadata_dict = assertion_metadata.get(key)
            self.assertDictContainsSubset(metadata_dict, fetched_dict)

        for key in ['schema:unknownMetadata']:
            self.assertEqual(response.data.get(key), assertion_metadata.get(key))

    @responses.activate
    def test_submit_basic_1_0_badge_image_datauri_png(self):
        setup_basic_1_0()
        setup_resources([
            {'url': OPENBADGES_CONTEXT_V1_URI, 'filename': 'v1_context.json'},
            {'url': OPENBADGES_CONTEXT_V2_URI, 'response_body': json.dumps(OPENBADGES_CONTEXT_V2_DICT)}
        ])
        self.setup_user(email='test@example.com', authenticate=True)

        image = open(os.path.join(CURRENT_DIRECTORY, 'testfiles/baked_image.png'))
        encoded = 'data:image/png;base64,' + base64.b64encode(image.read())
        post_input = {
            'image': encoded
        }
        response = self.client.post(
            '/v1/earner/badges', post_input, format='json'
        )
        self.assertEqual(response.status_code, 201)
        get_response = self.client.get('/v1/earner/badges')
        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(
            get_response.data[0].get('json', {}).get('id'), 'http://a.com/instance',
            "The badge in our backpack should report its JSON-LD id as its original OpenBadgeId"
        )
        # I think this test failure will be fixed by a badgecheck update to openbadges 1.0.1 as well

    @responses.activate
    def test_submit_basic_1_0_badge_assertion(self):
        setup_basic_1_0()
        setup_resources([
            {'url': OPENBADGES_CONTEXT_V1_URI, 'filename': 'v1_context.json'},
            {'url': OPENBADGES_CONTEXT_V2_URI, 'response_body': json.dumps(OPENBADGES_CONTEXT_V2_DICT)}
        ])
        self.setup_user(email='test@example.com', authenticate=True)

        post_input = {
            'assertion': open(os.path.join(CURRENT_DIRECTORY, 'testfiles/1_0_basic_instance.json')).read()
        }
        response = self.client.post(
            '/v1/earner/badges', post_input
        )
        self.assertEqual(response.status_code, 201)
        get_response = self.client.get('/v1/earner/badges')
        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(
            get_response.data[0].get('json', {}).get('id'), 'http://a.com/instance',
            "The badge in our backpack should report its JSON-LD id as its original OpenBadgeId"
        )

    @responses.activate
    def test_submit_basic_1_0_badge_url_variant_email(self):
        setup_basic_1_0(**{'exclude': 'http://a.com/instance'})
        setup_resources([
            {'url': 'http://a.com/instance3', 'filename': '1_0_basic_instance3.json'},
            {'url': OPENBADGES_CONTEXT_V1_URI, 'filename': 'v1_context.json'},
            {'url': OPENBADGES_CONTEXT_V2_URI, 'response_body': json.dumps(OPENBADGES_CONTEXT_V2_DICT)}
        ])
        self.setup_user(email='test@example.com', authenticate=True)

        # add variant explicitly
        response = self.client.post('/v1/user/emails', dict(
            email='TEST@example.com'
        ))
        self.assertEqual(response.status_code, 400)  # adding a variant successfully returns a 400

        post_input = {
            'url': 'http://a.com/instance3',
        }
        response = self.client.post(
            '/v1/earner/badges', post_input
        )
        self.assertEqual(response.status_code, 201)

        get_response = self.client.get('/v1/earner/badges')
        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(
            get_response.data[0].get('json', {}).get('id'),
            'http://a.com/instance3'
        )
        self.assertEqual(
            get_response.data[0].get('json', {}).get('recipient', {}).get('@value', {}).get('recipient'), 'TEST@example.com'
        )

        email = CachedEmailAddress.objects.get(email='test@example.com')
        self.assertTrue('TEST@example.com' in [e.email for e in email.cached_variants()])

    @responses.activate
    def test_submit_basic_1_0_badge_with_inaccessible_badge_image(self):
        setup_basic_1_0(**{'exclude': ['http://a.com/badgeclass_image']})
        setup_resources([
            {'url': OPENBADGES_CONTEXT_V1_URI, 'filename': 'v1_context.json'},
            {'url': OPENBADGES_CONTEXT_V2_URI, 'response_body': json.dumps(OPENBADGES_CONTEXT_V2_DICT)}
        ])
        self.setup_user(email='test@example.com', authenticate=True)

        post_input = {
            'url': 'http://a.com/instance'
        }
        response = self.client.post(
            '/v1/earner/badges', post_input
        )
        self.assertEqual(response.status_code, 400)
        self.assertIsNotNone(first_node_match(response.data, dict(
            messageLevel='ERROR',
            name='IMAGE_VALIDATION'
        )))

    @responses.activate
    def test_submit_basic_1_0_badge_missing_issuer(self):
        setup_basic_1_0(**{'exclude': ['http://a.com/issuer']})
        setup_resources([
            {'url': OPENBADGES_CONTEXT_V1_URI, 'filename': 'v1_context.json'},
            {'url': OPENBADGES_CONTEXT_V2_URI, 'response_body': json.dumps(OPENBADGES_CONTEXT_V2_DICT)}
        ])
        self.setup_user(email='test@example.com', authenticate=True)

        post_input = {
            'url': 'http://a.com/instance'
        }
        response = self.client.post(
            '/v1/earner/badges', post_input
        )
        self.assertEqual(response.status_code, 400)
        self.assertIsNotNone(first_node_match(response.data, dict(
            messageLevel='ERROR',
            name='FETCH_HTTP_NODE'
        )))

    @responses.activate
    def test_submit_basic_1_0_badge_missing_badge_prop(self):
        self.setup_user(email='test@example.com', authenticate=True)

        responses.add(
            responses.GET, 'http://a.com/instance',
            body=open(os.path.join(CURRENT_DIRECTORY, 'testfiles/1_0_basic_instance_missing_badge_prop.json')).read(),
            status=200, content_type='application/json'
        )
        setup_resources([
            {'url': OPENBADGES_CONTEXT_V1_URI, 'filename': 'v1_context.json'},
            {'url': OPENBADGES_CONTEXT_V2_URI, 'response_body': json.dumps(OPENBADGES_CONTEXT_V2_DICT)}
        ])

        post_input = {
            'url': 'http://a.com/instance'
        }

        response = self.client.post(
            '/v1/earner/badges', post_input
        )

        self.assertEqual(response.status_code, 400)
        self.assertIsNotNone(first_node_match(response.data, dict(
            messageLevel='ERROR',
            name='VALIDATE_PROPERTY',
            prop_name='badge'
        )))

    @responses.activate
    def test_submit_basic_0_5_0_badge_via_url(self):
        setup_basic_0_5_0()
        setup_resources([
            {'url': OPENBADGES_CONTEXT_V1_URI, 'filename': 'v1_context.json'},
            {'url': OPENBADGES_CONTEXT_V2_URI, 'response_body': json.dumps(OPENBADGES_CONTEXT_V2_DICT)}
        ])
        self.setup_user(email='test@example.com', authenticate=True)

        post_input = {
            'url': 'http://oldstyle.com/instance'
        }
        response = self.client.post(
            '/v1/earner/badges', post_input
        )
        self.assertEqual(response.status_code, 201)
        get_response = self.client.get('/v1/earner/badges')
        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(get_response.data[0].get('json', {}).get('id'), post_input.get('url'),
                         "The badge in our backpack should report its JSON-LD id as the original OpenBadgeId")

    @responses.activate
    def test_submit_0_5_badge_upload_by_assertion(self):
        setup_basic_0_5_0()
        setup_resources([
            {'url': OPENBADGES_CONTEXT_V1_URI, 'filename': 'v1_context.json'},
            {'url': OPENBADGES_CONTEXT_V2_URI, 'response_body': json.dumps(OPENBADGES_CONTEXT_V2_DICT)}
        ])
        self.setup_user(email='test@example.com', authenticate=True)

        post_input = {
            'assertion': open(os.path.join(CURRENT_DIRECTORY, 'testfiles', '0_5_basic_instance.json')).read()
        }
        response = self.client.post(
            '/v1/earner/badges', post_input
        )
        self.assertEqual(response.status_code, 400)
        # TODO Update to support 0.5 badges

    @responses.activate
    def test_creating_no_duplicate_badgeclasses_and_issuers(self):
        setup_basic_1_0()
        setup_resources([
            {'url': 'http://a.com/instance2', 'filename': '1_0_basic_instance2.json'},
            {'url': OPENBADGES_CONTEXT_V1_URI, 'filename': 'v1_context.json'},
            {'url': OPENBADGES_CONTEXT_V2_URI, 'response_body': json.dumps(OPENBADGES_CONTEXT_V2_DICT)}
        ])
        self.setup_user(email='test@example.com', authenticate=True)

        badgeclass_count = BadgeClass.objects.all().count()
        issuer_count = Issuer.objects.all().count()

        post_input = {
            'url': 'http://a.com/instance'
        }
        response = self.client.post(
            '/v1/earner/badges', post_input
        )
        self.assertEqual(response.status_code, 201)

        post2_input = {
            'url': 'http://a.com/instance2'
        }
        response2 = self.client.post(
           '/v1/earner/badges', post2_input
        )
        self.assertEqual(response2.status_code, 201)

        self.assertEqual(BadgeClass.objects.all().count(), badgeclass_count+1)
        self.assertEqual(Issuer.objects.all().count(), issuer_count+1)

    def test_shouldnt_access_already_stored_badgeclass_for_validation(self):
        """
        TODO: If we already have a LocalBadgeClass saved for a URL,
        don't bother fetching again too soon.
        """
        pass

    def test_should_recheck_stale_localbadgeclass_in_validation(self):
        """
        TODO: If it has been more than a month since we last examined a LocalBadgeClass,
        maybe we should check
        it again.
        """
        pass
        # TODO: Re-evaluate badgecheck caching strategy

    @responses.activate
    def test_submit_badge_assertion_with_bad_date(self):
        setup_basic_1_0()
        setup_resources([
            {'url': 'http://a.com/instancebaddate', 'filename': '1_0_basic_instance_with_bad_date.json'},
            {'url': OPENBADGES_CONTEXT_V1_URI, 'filename': 'v1_context.json'},
            {'url': OPENBADGES_CONTEXT_V2_URI, 'response_body': json.dumps(OPENBADGES_CONTEXT_V2_DICT)}
        ])
        self.setup_user(email='test@example.com', authenticate=True)

        post_input = {
            'url': 'http://a.com/instancebaddate'
        }
        response = self.client.post(
            '/v1/earner/badges', post_input
        )
        self.assertEqual(response.status_code, 400)

        self.assertIsNotNone(first_node_match(response.data, dict(
            messageLevel='ERROR',
            name='VALIDATE_PROPERTY',
            prop_name='issuedOn'
        )))

    @responses.activate
    def test_submit_badge_invalid_component_json(self):
        setup_basic_1_0(**{'exclude': ['http://a.com/issuer']})
        setup_resources([
            {'url': 'http://a.com/issuer', 'filename': '1_0_basic_issuer_invalid_json.json'},
            {'url': OPENBADGES_CONTEXT_V1_URI, 'filename': 'v1_context.json'},
            {'url': OPENBADGES_CONTEXT_V2_URI, 'response_body': json.dumps(OPENBADGES_CONTEXT_V2_DICT)}
        ])
        self.setup_user(email='test@example.com', authenticate=True)

        post_input = {
            'url': 'http://a.com/instance'
        }
        response = self.client.post(
            '/v1/earner/badges', post_input
        )
        self.assertEqual(response.status_code, 400)

        self.assertIsNotNone(first_node_match(response.data, dict(
            messageLevel='ERROR',
            name='FETCH_HTTP_NODE'
        )))

    @responses.activate
    def test_submit_badge_invalid_assertion_json(self):
        setup_resources([
            {'url': 'http://a.com/instance', 'filename': '1_0_basic_issuer_invalid_json.json'},
            {'url': OPENBADGES_CONTEXT_V1_URI, 'filename': 'v1_context.json'},
            {'url': OPENBADGES_CONTEXT_V2_URI, 'response_body': json.dumps(OPENBADGES_CONTEXT_V2_DICT)}
        ])
        self.setup_user(email='test@example.com', authenticate=True)

        post_input = {
            'url': 'http://a.com/instance'
        }
        response = self.client.post(
            '/v1/earner/badges', post_input
        )
        self.assertEqual(response.status_code, 400)

        # openbadges returns FETCH_HTTP_NODE error when retrieving invalid json
        self.assertIsNotNone(first_node_match(response.data, dict(
            messageLevel='ERROR',
            name='FETCH_HTTP_NODE'
        )))

    @responses.activate
    def test_submit_badges_with_intragraph_references(self):
        setup_resources([
            {'url': 'http://a.com/assertion-embedded1', 'filename': '2_0_assertion_embedded_badgeclass.json'},
            {'url': OPENBADGES_CONTEXT_V2_URI, 'response_body': json.dumps(OPENBADGES_CONTEXT_V2_DICT)},
            {'url': 'http://a.com/badgeclass_image', 'filename': "unbaked_image.png"},
        ])
        self.setup_user(email='test@example.com', authenticate=True)

        assertion = {
            "@context": 'https://w3id.org/openbadges/v2',
            "id": 'http://a.com/assertion-embedded1',
            "type": "Assertion",
        }
        post_input = {
            'assertion': json.dumps(assertion)
        }
        response = self.client.post('/v1/earner/badges', post_input, format='json')
        self.assertEqual(response.status_code, 201)

    @responses.activate
    def test_submit_basic_1_0_badge_via_url_delete_and_readd(self):
        setup_basic_1_0()
        setup_resources([
            {'url': OPENBADGES_CONTEXT_V1_URI, 'filename': 'v1_context.json'},
            {'url': OPENBADGES_CONTEXT_V2_URI, 'response_body': json.dumps(OPENBADGES_CONTEXT_V2_DICT)}
        ])
        self.setup_user(email='test@example.com', token_scope='rw:backpack')

        post_input = {
            'url': 'http://a.com/instance'
        }
        response = self.client.post(
            '/v1/earner/badges', post_input
        )
        self.assertEqual(response.status_code, 201)
        get_response = self.client.get('/v1/earner/badges')
        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(
            get_response.data[0].get('json', {}).get('id'), 'http://a.com/instance',
            "The badge in our backpack should report its JSON-LD id as its original OpenBadgeId"
        )

        new_instance = BadgeInstance.objects.first()
        expected_url = "{}{}".format(OriginSetting.HTTP,
                                     reverse('badgeinstance_image', kwargs=dict(entity_id=new_instance.entity_id)))
        self.assertEqual(get_response.data[0].get('json', {}).get('image', {}).get('id'), expected_url)

        response = self.client.delete('/v1/earner/badges/{}'.format(new_instance.entity_id))
        self.assertEqual(response.status_code, 204)
        self.assertEqual(BadgeInstance.objects.count(), 0)

        response = self.client.post(
            '/v1/earner/badges', post_input
        )
        self.assertEqual(response.status_code, 201)


class TestDeleteLocalAssertion(BadgrTestCase, SetupIssuerHelper):
    @responses.activate
    def test_can_delete_local(self):
        test_issuer_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_issuer_user)
        test_badgeclass = self.setup_badgeclass(issuer=test_issuer)

        test_recipient = self.setup_user(email='test_recipient@email.test', authenticate=True)
        assertion = test_badgeclass.issue(recipient_id='test_recipient@email.test', recipient_type='email')

        response = self.client.get(
            '/v1/earner/badges'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1, "There is a badge in the recipient's backpack")

        response = self.client.delete('/v1/earner/badges/{}'.format(assertion.entity_id))
        self.assertEqual(response.status_code, 204)
        self.assertEqual(BadgeInstance.objects.count(), 1)
        assertion = BadgeInstance.objects.get(pk=assertion.pk)
        self.assertEqual(assertion.acceptance, BadgeInstance.ACCEPTANCE_REJECTED)

        response = self.client.get(
            '/v1/earner/badges'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0, "There is no longer a badge in the recipient's backpack")

        setup_resources([
            {'url': OPENBADGES_CONTEXT_V1_URI, 'filename': 'v1_context.json'},
            {'url': OPENBADGES_CONTEXT_V2_URI, 'response_body': json.dumps(OPENBADGES_CONTEXT_V2_DICT)},
            {'url': assertion.jsonld_id, 'response_body': json.dumps(assertion.get_json())},
            {
                'url': assertion.jsonld_id + '/image',
                'response_body': assertion.image.read(),
                'content-type': 'image/png'
            },
            {'url': test_badgeclass.jsonld_id, 'response_body': json.dumps(test_badgeclass.get_json())},
            {
                'url': test_badgeclass.jsonld_id + '/image',
                'response_body': test_badgeclass.image.read(),
                'content-type': 'image/png'
            },
            {'url': test_issuer.jsonld_id, 'response_body': json.dumps(test_issuer.get_json())}
        ])

        post_input = {
            'url': assertion.jsonld_id
        }
        response = self.client.post(
            '/v1/earner/badges', post_input
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['id'], assertion.entity_id)
        get_response = self.client.get('/v1/earner/badges')
        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(len(get_response.data), 1)


class TestExpandAssertions(BadgrTestCase, SetupIssuerHelper):
    def test_no_expands(self):
        '''Expect correct result if no expand parameters are passed in'''

        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)
        test_badgeclass = self.setup_badgeclass(issuer=test_issuer)

        test_recipient = self.setup_user(email='test_recipient@email.test', authenticate=True)
        test_badgeclass.issue(recipient_id='test_recipient@email.test')

        response = self.client.get('/v2/backpack/assertions')

        self.assertEqual(response.status_code, 200)
        # checking if 'badgeclass' was expanded into a dictionary
        self.assertTrue(not isinstance(response.data['result'][0]['badgeclass'], collections.OrderedDict))

        fid = response.data['result'][0]['entityId']
        response = self.client.get('/v2/backpack/assertions/{}'.format(fid))
        self.assertEqual(response.status_code, 200)

    def test_expand_badgeclass_single_assertion_single_issuer(self):
        '''For a client with a single badge, attempting to expand the badgeclass without
        also expanding the issuer.'''

        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)
        test_badgeclass = self.setup_badgeclass(issuer=test_issuer)

        test_recipient = self.setup_user(email='test_recipient@email.test', authenticate=True)
        test_badgeclass.issue(recipient_id='test_recipient@email.test')

        response = self.client.get('/v2/backpack/assertions?expand=badgeclass')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response.data['result'][0]['badgeclass'], collections.OrderedDict))
        self.assertTrue(not isinstance(response.data['result'][0]['badgeclass']['issuer'], collections.OrderedDict))

        fid = response.data['result'][0]['entityId']
        response = self.client.get('/v2/backpack/assertions/{}?expand=badgeclass&expand=issuer'.format(fid))
        self.assertEqual(response.status_code, 200)

        self.assertTrue(isinstance(response.data['result'][0]['badgeclass'], dict))

    def test_expand_issuer_single_assertion_single_issuer(self):
        '''For a client with a single badge, attempting to expand the issuer without
        also expanding the badgeclass should result in no expansion to the response.'''

        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)
        test_badgeclass = self.setup_badgeclass(issuer=test_issuer)

        test_recipient = self.setup_user(email='test_recipient@email.test', authenticate=True)
        test_badgeclass.issue(recipient_id='test_recipient@email.test')

        responseOne = self.client.get('/v2/backpack/assertions?expand=issuer')
        responseTwo = self.client.get('/v2/backpack/assertions')

        self.assertEqual(responseOne.status_code, 200)
        self.assertEqual(responseTwo.status_code, 200)
        self.assertEqual(responseOne.data, responseTwo.data)

    def test_expand_badgeclass_and_isser_single_assertion_single_issuer(self):
        '''For a client with a single badge, attempting to expand the badgeclass and issuer.'''

        test_user = self.setup_user(authenticate=True)
        test_issuer = self.setup_issuer(owner=test_user)
        test_badgeclass = self.setup_badgeclass(issuer=test_issuer)

        test_recipient = self.setup_user(email='test_recipient@email.test', authenticate=True)
        test_badgeclass.issue(recipient_id='test_recipient@email.test')

        response = self.client.get('/v2/backpack/assertions?expand=badgeclass&expand=issuer')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response.data['result'][0]['badgeclass'], collections.OrderedDict))
        self.assertTrue(isinstance(response.data['result'][0]['badgeclass']['issuer'], collections.OrderedDict))

    def test_expand_badgeclass_mult_assertions_mult_issuers(self):
        '''For a client with multiple badges, attempting to expand the badgeclass without
        also expanding the issuer.'''

        # define users and issuers
        test_user = self.setup_user(email='test_recipient@email.test', authenticate=True)
        test_issuer_one = self.setup_issuer(name="Test Issuer 1",owner=test_user)
        test_issuer_two = self.setup_issuer(name="Test Issuer 2",owner=test_user)
        test_issuer_three = self.setup_issuer(name="Test Issuer 3",owner=test_user)

        # define badgeclasses
        test_badgeclass_one = self.setup_badgeclass(name='Test Badgeclass 1',issuer=test_issuer_one)
        test_badgeclass_two = self.setup_badgeclass(name='Test Badgeclass 2',issuer=test_issuer_one)
        test_badgeclass_three = self.setup_badgeclass(name='Test Badgeclass 3',issuer=test_issuer_two)
        test_badgeclass_four = self.setup_badgeclass(name='Test Badgeclass 4',issuer=test_issuer_three)
        test_badgeclass_five = self.setup_badgeclass(name='Test Badgeclass 5',issuer=test_issuer_three)
        test_badgeclass_six = self.setup_badgeclass(name='Test Badgeclass 6',issuer=test_issuer_three)

        # issue badges to user
        test_badgeclass_one.issue(recipient_id='test_recipient@email.test')
        test_badgeclass_one.issue(recipient_id='test_recipient@email.test')
        test_badgeclass_one.issue(recipient_id='test_recipient@email.test')
        test_badgeclass_one.issue(recipient_id='test_recipient@email.test')
        test_badgeclass_one.issue(recipient_id='test_recipient@email.test')
        test_badgeclass_one.issue(recipient_id='test_recipient@email.test')

        response = self.client.get('/v2/backpack/assertions?expand=badgeclass')

        self.assertEqual(len(response.data['result']), 6)
        for i in range(6):
            self.assertTrue(isinstance(response.data['result'][i]['badgeclass'], collections.OrderedDict))
            self.assertTrue(not isinstance(response.data['result'][i]['badgeclass']['issuer'], collections.OrderedDict))

    def test_expand_badgeclass_and_issuer_mult_assertions_mult_issuers(self):
        '''For a client with multiple badges, attempting to expand the badgeclass and issuer.'''

        # define users and issuers
        test_user = self.setup_user(email='test_recipient@email.test', authenticate=True)
        test_issuer_one = self.setup_issuer(name="Test Issuer 1",owner=test_user)
        test_issuer_two = self.setup_issuer(name="Test Issuer 2",owner=test_user)
        test_issuer_three = self.setup_issuer(name="Test Issuer 3",owner=test_user)

        # define badgeclasses
        test_badgeclass_one = self.setup_badgeclass(name='Test Badgeclass 1',issuer=test_issuer_one)
        test_badgeclass_two = self.setup_badgeclass(name='Test Badgeclass 2',issuer=test_issuer_one)
        test_badgeclass_three = self.setup_badgeclass(name='Test Badgeclass 3',issuer=test_issuer_two)
        test_badgeclass_four = self.setup_badgeclass(name='Test Badgeclass 4',issuer=test_issuer_three)
        test_badgeclass_five = self.setup_badgeclass(name='Test Badgeclass 5',issuer=test_issuer_three)
        test_badgeclass_six = self.setup_badgeclass(name='Test Badgeclass 6',issuer=test_issuer_three)

        # issue badges to user
        test_badgeclass_one.issue(recipient_id='test_recipient@email.test')
        test_badgeclass_one.issue(recipient_id='test_recipient@email.test')
        test_badgeclass_one.issue(recipient_id='test_recipient@email.test')
        test_badgeclass_one.issue(recipient_id='test_recipient@email.test')
        test_badgeclass_one.issue(recipient_id='test_recipient@email.test')
        test_badgeclass_one.issue(recipient_id='test_recipient@email.test')

        response = self.client.get('/v2/backpack/assertions?expand=badgeclass&expand=issuer')

        self.assertEqual(len(response.data['result']), 6)
        for i in range(6):
            self.assertTrue(isinstance(response.data['result'][i]['badgeclass'], collections.OrderedDict))
            self.assertTrue(isinstance(response.data['result'][i]['badgeclass']['issuer'], collections.OrderedDict))


class TestPendingBadges(BadgrTestCase, SetupIssuerHelper):
    @responses.activate
    def test_view_badge_i_imported(self):
        setup_resources([
            {'url': 'http://a.com/assertion-embedded1', 'filename': '2_0_assertion_embedded_badgeclass.json'},
            {'url': OPENBADGES_CONTEXT_V2_URI, 'response_body': json.dumps(OPENBADGES_CONTEXT_V2_DICT)},
            {'url': 'http://a.com/badgeclass_image', 'filename': "unbaked_image.png"},
        ])
        unverified_email = 'test@example.com'
        test_user = self.setup_user(email='verified@example.com', authenticate=True)
        CachedEmailAddress.objects.add_email(test_user, unverified_email)
        post_input = {"url": "http://a.com/assertion-embedded1"}

        post_resp = self.client.post('/v2/backpack/import', post_input, format='json')
        assertion = BadgeInstance.objects.first()

        test_issuer_one = self.setup_issuer(name="Test Issuer 1", owner=test_user)
        test_badgeclass_one = self.setup_badgeclass(name='Test Badgeclass 1', issuer=test_issuer_one)
        test_badgeclass_one.issue(recipient_id='verified@example.com')
        
        get_resp = self.client.get('/v2/backpack/assertions?include_pending=1')
        
        self.assertEqual(post_resp.status_code, 201)

        self.assertEqual(get_resp.status_code, 200)
        self.assertEqual(len(get_resp.data.get('result')), 2)
        self.assertTrue(get_resp.data.get('result')[0]['pending'])
        self.assertFalse(get_resp.data.get('result')[1]['pending'])

        get_resp = self.client.get('/v1/earner/badges?json_format=plain&include_pending=1')
        self.assertEqual(len(get_resp.data), 2)
        self.assertTrue(get_resp.data[0]['pending'])
        self.assertFalse(get_resp.data[1]['pending'])

        get_resp = self.client.get('/v1/earner/badges?json_format=plain&include_pending=0')
        self.assertEqual(len(get_resp.data), 1)

        # User should be able to delete it as well
        del_resp = self.client.delete('/v2/backpack/assertions/{}'.format(assertion.entity_id))
        self.assertEqual(del_resp.status_code, 204)

        get_resp = self.client.get('/v1/earner/badges?json_format=plain&include_pending=1')
        self.assertEqual(len(get_resp.data), 1)

    @responses.activate
    def test_view_badge_i_imported_with_v1(self):
        setup_resources([
            {'url': 'http://a.com/assertion-embedded1', 'filename': '2_0_assertion_embedded_badgeclass.json'},
            {'url': OPENBADGES_CONTEXT_V2_URI, 'response_body': json.dumps(OPENBADGES_CONTEXT_V2_DICT)},
            {'url': 'http://a.com/badgeclass_image', 'filename': "unbaked_image.png"},
        ])
        unverified_email = 'test@example.com'
        test_user = self.setup_user(email='verified@example.com', authenticate=True)
        CachedEmailAddress.objects.add_email(test_user, unverified_email)
        post_input = {"url": "http://a.com/assertion-embedded1"}
        post_resp = self.client.post('/v1/earner/badges', post_input, format='json')
        self.assertEqual(post_resp.status_code, 201)
        assertion = BadgeInstance.objects.first()

        get_resp2 = self.client.get('/v1/earner/badges?json_format=plain')
        self.assertEqual(len(get_resp2.data), 0)
        
        get_resp3 = self.client.get('/v1/earner/badges?json_format=plain&include_pending=1')
        self.assertEqual(len(get_resp3.data), 1)

        get_resp4 = self.client.get('/v1/earner/badges?json_format=plain&include_pending=false')
        self.assertEqual(len(get_resp4.data), 0)

        # User should be able to delete it as well
        del_resp = self.client.delete('/v1/earner/badges/{}'.format(assertion.entity_id))
        self.assertEqual(del_resp.status_code, 204)

    # apps.badgeuser.tests.UserRecipientIdentifierTests.test_verified_recipient_v2_assertions_endpoint
    # apps.badgeuser.tests.UserRecipientIdentifierTests.test_verified_recipient_v1_badges_endpoint

    def test_cant_view_badge_awarded_to_unverified_that_i_did_not_import(self):
        unverified_email = 'test@example.com'
        test_user = self.setup_user(email='verified@example.com', authenticate=True)
        CachedEmailAddress.objects.add_email(test_user, unverified_email)
        test_issuer_one = self.setup_issuer(name="Test Issuer 1", owner=test_user)
        test_badgeclass_one = self.setup_badgeclass(name='Test Badgeclass 1', issuer=test_issuer_one)
        test_badgeclass_one.issue(recipient_id='test@example.com', recipient_type='email')
        get_resp = self.client.get('/v2/backpack/assertions?include_pending=1')
        
        self.assertEqual(get_resp.status_code, 200)
        self.assertEqual(len(get_resp.data.get('result')), 0)
        
        get_resp2 = self.client.get('/v1/earner/badges?json_format=plain')
        self.assertEqual(get_resp2.status_code, 200)
        self.assertEqual(len(get_resp2.data), 0)
