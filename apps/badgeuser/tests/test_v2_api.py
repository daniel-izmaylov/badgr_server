from django.core.urlresolvers import reverse
from mainsite.tests import SetupIssuerHelper, BadgrTestCase
from django.utils import timezone
from oauth2_provider.models import Application, RefreshToken
from mainsite.models import AccessTokenProxy, ApplicationInfo


class AccessTokenHandling(SetupIssuerHelper, BadgrTestCase):
    def test_token_deletion(self):
        staff = self.setup_user(email='staff@example.com', authenticate=True)
        clientAppUser = self.setup_user(email='clientApp@example.com', token_scope='r:assertions')
        app = Application.objects.create(
            client_id='clientApp-authcode', client_secret='testsecret', authorization_grant_type='authorization-code',
            user=clientAppUser)
        ApplicationInfo.objects.create(application=app, allowed_scopes='r:assertions', trust_email_verification=True)

        t = AccessTokenProxy.objects.create(
            user=staff, scope='rw:issuer r:profile r:backpack', expires=timezone.now() + timezone.timedelta(hours=1),
            token='123', application=app
        )
        RefreshToken.objects.create(access_token=t, user_id=staff.pk, application_id=app.pk)
        url = reverse('v2_api_access_token_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        # Delete tokens in response
        url = reverse('v2_api_access_token_detail', kwargs={'entity_id': response.data[0]['entityId']})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(len(RefreshToken.objects.all()), 0)
