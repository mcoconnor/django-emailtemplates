from django.core import mail
from django.test import TestCase
from django.contrib.sites.models import Site
from django.contrib.contenttypes.models import ContentType
from django.template import Context

from models import EmailMessageTemplate, Log


class TemplateRetrievalTest(TestCase):
    """
    Ensure that template objects are retrieved correctly from the database based 
    on queries by name and object, respecting the enabled flag and the fallback 
    behavior for object-based queries.  Queries that do not match active 
    templates should raise exceptions.
    """
    fixtures = ['test_templates',]

    # Simple named template retrievals
    def test_retrieve_named_template(self):
        """Ensure the correct named template is returned"""
        template = EmailMessageTemplate.objects.get_template("Template 1")
        self.assertEqual(template.pk, 1)

    def test_retrieve_missing_named_template(self):
        """Ensure an exception is raised if the correct template is missing"""
        self.assertRaisesMessage(EmailMessageTemplate.DoesNotExist,
            "EmailMessageTemplate matching query does not exist.",
            lambda: EmailMessageTemplate.objects.get_template("Nonexistent Template"))

    def test_retrieve_disabled_named_template(self):
        """Ensure an exception is raised if the correct template is disabled"""
        self.assertRaisesMessage(EmailMessageTemplate.DoesNotExist,
            "EmailMessageTemplate matching query does not exist.",
            lambda: EmailMessageTemplate.objects.get_template("Template 3"))

    # Retrievals of templates with specified objects
    def test_retrieve_object_template(self):
        """"Ensure the correct template is returned when queried with name and object"""
        site = Site.objects.get(pk=1)
        template = EmailMessageTemplate.objects.get_template("Template 1", related_object=site)
        self.assertEqual(template.pk, 4)

    def test_retrieve_missing_object_template(self):
        """Ensure an exception is raised if a template specifed with bad name and object is missing"""
        site = Site.objects.get(pk=1)
        self.assertRaisesMessage(EmailMessageTemplate.DoesNotExist,
            "EmailMessageTemplate matching query does not exist.",
            lambda: EmailMessageTemplate.objects.get_template("Nonexistent Template", site))

    def test_retrieve_object_fallback_template(self):
        """
        Ensure the fallback (no object) template is returned if a template with
        the specifed object is missing
        """
        site = Site.objects.get(pk=2)
        template = EmailMessageTemplate.objects.get_template("Template 1", related_object=site)
        self.assertEqual(template.pk, 1)

    def test_retrieve_disabled_object_fallback_template(self):
        """
        Ensure the fallback (no object) template is returned if a template with
        the specifed object is disabled
        """
        site = Site.objects.get(pk=2)
        template = EmailMessageTemplate.objects.get_template("Template 2", related_object=site)
        self.assertEqual(template.pk, 2)


class TemplatePreparationTest(TestCase):
    """
    Ensure that template data is correctly produced when a template is 
    instantiated and prepared for sending.  This includes assemling the From, CC 
    and BCC address lists and rendering the subject and body templates. 
    """
    fixtures = ['test_templates',]
    context = {'hello': '*HELLO*', 'world': '*WORLD*'}

    # Ensure the sender address is set correctly
    def test_default_from(self):
        """
        If not specified in the template or on the instance, the from address is 
        pulled from settings.  If specified, this will be the 
        EMAILTEMPLATES_DEFAULT_FROM_EMAIL setting, else the DEFAULT_FROM_EMAIL 
        setting.
        """
        template = EmailMessageTemplate.objects.get_template("Template 1")
        with self.settings(DEFAULT_FROM_EMAIL='test1@example.com'):
            self.assertEqual(template.from_email, 'test1@example.com')
            with self.settings(EMAILTEMPLATES_DEFAULT_FROM_EMAIL='test2@example.com'):
                self.assertEqual(template.from_email, 'test2@example.com')

    def test_from_setter(self):
        """
        The 'from' setter shouldn't affect anything (to prevent EmailMessage 
        from messing with the template values).
        """
        template = EmailMessageTemplate.objects.get_template("Template 1")
        with self.settings(DEFAULT_FROM_EMAIL='test1@example.com'):
            template.from_email = 'dontdoit@example.com'
            self.assertEqual(template.from_email, 'test1@example.com')

    def test_template_specified_from(self):
        """
        If a from address is specified on the template, use that instead.
        """
        template = EmailMessageTemplate.objects.get_template("Template 2")
        with self.settings(DEFAULT_FROM_EMAIL='dontdoit@example.com'):
            self.assertEqual(template.from_email, 'example@example.com')

    def test_prepare_specified_from(self):
        """
        If a from address is specified on the template, use that instead.
        """
        template = EmailMessageTemplate.objects.get_template("Template 2")
        with self.settings(DEFAULT_FROM_EMAIL='dontdoit@example.com'):
            template.prepare(from_email='inprepare@example.com')
            self.assertEqual(template.from_email, 'inprepare@example.com')
    # Ensure the "to" address is set correctly

    def test_instance_to(self):
        """Ensure the "to" email set on the instance is used"""
        template = EmailMessageTemplate.objects.get_template("Template 2")
        template.to = ['inprepare@example.com']
        self.assertEqual(template.to, ['inprepare@example.com'])
    # Ensure the "CC" address list is set correctly

    def test_instance_cc(self):
        """Ensure the "cc" email list set o the instance is used"""
        template = EmailMessageTemplate.objects.get_template("Template 1")
        template.cc = ['inprepare@example.com', 'inprepare2@example.com']
        cc = template.cc
        cc.sort()
        self.assertEqual(cc, ['inprepare2@example.com', 'inprepare@example.com'])

    def test_template_cc(self):
        """
        Ensure the "cc" email list set in the template is used
        """
        template = EmailMessageTemplate.objects.get_template("Template 2")
        cc = template.cc
        cc.sort()
        self.assertEqual(cc, ['a@example.com', 'b@example.com'])

    def test_instance_template_cc(self):
        """
        Ensure the "cc" email list seton the instance is used in 
        conjunction with cc addresses in the template
        """
        template = EmailMessageTemplate.objects.get_template("Template 2")
        template.cc = ['inprepare@example.com', 'inprepare2@example.com']
        cc = template.cc
        cc.sort()
        self.assertEqual(cc, ['a@example.com', 'b@example.com',
                              'inprepare2@example.com', 'inprepare@example.com'])

    # Ensure the "BCC" address list is set correctly
    def test_instance_bcc(self):
        """Ensure the "bcc" email list set on the instance is used"""
        template = EmailMessageTemplate.objects.get_template("Template 1")
        template.bcc = ['inprepare@example.com', 'inprepare2@example.com']
        bcc = template.bcc
        bcc.sort()
        self.assertEqual(bcc, ['inprepare2@example.com', 'inprepare@example.com'])

    def test_template_bcc(self):
        """
        Ensure the "bcc" email list set in the template is used
        """
        template = EmailMessageTemplate.objects.get_template("Template 2")
        bcc = template.bcc
        bcc.sort()
        self.assertEqual(bcc, ['c@example.com', 'd@example.com'])

    def test_instance_template_bcc(self):
        """
        Ensure the "bcc" email list set on the instance is used in 
        conjunction with bcc addresses in the template
        """
        template = EmailMessageTemplate.objects.get_template("Template 2")
        template.bcc = ['inprepare@example.com', 'inprepare2@example.com']
        bcc = template.bcc
        bcc.sort()
        self.assertEqual(bcc, ['c@example.com', 'd@example.com',
                               'inprepare2@example.com', 'inprepare@example.com'])
    # Ensure the subject renders correctly

    def test_render_subject_template(self):
        """
        Ensure the subject renders as expected 
        """
        template = EmailMessageTemplate.objects.get_template("Template 1")
        template.context = self.context
        self.assertEqual(template.subject, "Test 1 Subject *HELLO*")

    def test_render_prefixed_subject_template(self):
        """
        Ensure the subject renders as expected with a specified prefix
        """
        template = EmailMessageTemplate.objects.get_template("Template 1")
        template.context = self.context
        template.subject_prefix = "[PREFIX] "
        self.assertEqual(template.subject, "[PREFIX] Test 1 Subject *HELLO*")
    # Ensure the body renders correctly

    def test_render_body_template(self):
        """
        Ensure the body renders as expected 
        """
        template = EmailMessageTemplate.objects.get_template("Template 1")
        template.context = self.context
        self.assertEqual(template.body, "Test 1 body *WORLD*")
    #Ensure the prepare method populates the message correctly

    def test_prepare_template(self):
        """
        Ensure the email parameters are set correctly by the prepare method 
        """
        template = EmailMessageTemplate.objects.get_template("Template 1")
        template.prepare(context=self.context,
                         from_email='from@example.com',
                         to=['to@example.com'],
                         cc=['cc@example.com'],
                         bcc=['bcc@example.com'],
                         subject_prefix='[PREFIX] ')
        self.assertEqual(template.subject, "[PREFIX] Test 1 Subject *HELLO*")
        self.assertEqual(template.body, "Test 1 body *WORLD*")
        self.assertEqual(template.from_email, 'from@example.com')
        self.assertEqual(template.to, ['to@example.com'])
        self.assertEqual(template.cc, ['cc@example.com'])
        self.assertEqual(template.bcc, ['bcc@example.com'])


class TemplateSendingTest(TestCase):
    """
    Ensure that the emails are actually composed and sent successfully and that 
    logs are generated (or not) when appropriate
    """
    fixtures = ['test_templates',]
    context = {'hello': '*HELLO*', 'world': '*WORLD*'}

    # Email sending
    def test_send_email_success(self):
        """Ensure that an email can be successfully sent to the outbox"""
        template = EmailMessageTemplate.objects.get_template("Template 1")
        template.prepare(context=self.context,
                         from_email='from@example.com',
                         to=['to@example.com'],
                         cc=['cc@example.com'],
                         bcc=['bcc@example.com'],
                         subject_prefix='[PREFIX] ')

        template.send()

        # Test that one message has been sent.
        self.assertEqual(len(mail.outbox), 1)

        # Verify that the subject of the first message is correct.
        self.assertEqual(mail.outbox[0].subject, '[PREFIX] Test 1 Subject *HELLO*')
        self.assertEqual(mail.outbox[0].body, "Test 1 body *WORLD*")
        self.assertEqual(mail.outbox[0].from_email, 'from@example.com')
        self.assertEqual(mail.outbox[0].to, ['to@example.com'])
        self.assertEqual(mail.outbox[0].cc, ['cc@example.com'])
        self.assertEqual(mail.outbox[0].bcc, ['bcc@example.com'])     

    # Message logging
    def test_logged_email(self): 
        template = EmailMessageTemplate.objects.get_template("Template 1")
        template.prepare(context=self.context,
                         from_email='from@example.com',
                         to=['to@example.com'],
                         cc=['cc@example.com'],
                         bcc=['bcc@example.com'],
                         subject_prefix='[PREFIX] ')

        template.send()
        
        logs = Log.objects.all()
        self.assertEqual(len(logs),1)
        self.assertEqual(logs[0].template.id,template.id)
        self.assertEqual(logs[0].message,'')
        self.assertEqual(logs[0].status,Log.STATUS.SUCCESS)
        self.assertEqual(logs[0].recipients,['to@example.com', 'cc@example.com', 
                                             'bcc@example.com'])

    def test_log_suppressed_setting(self): 
        with self.settings(EMAILTEMPLATES_LOG_EMAILS=False):
            template = EmailMessageTemplate.objects.get_template("Template 1")
            template.prepare(context=self.context, to=['to@example.com'])
            template.send()
        
            logs = Log.objects.all()
            self.assertEqual(len(logs),0)

    def test_log_suppressed_template(self): 
        template = EmailMessageTemplate.objects.get_template("Template 4")
        template.prepare(context=self.context, to=['to@example.com'])
        template.send()
        
        logs = Log.objects.all()
        self.assertEqual(len(logs),0)

class TemplateValidatorTest(TestCase):
    pass


class UtilityFunctionTest(TestCase):
    pass


class ManagementCommandsTest(TestCase):
    pass