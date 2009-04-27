# -*- coding: UTF-8 -*-
# Copyright (C) 2005-2008 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2007 Henry Obein <henry@itaapy.com>
# Copyright (C) 2007 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2007-2008 Sylvain Taverne <sylvain@itaapy.com>
# Copyright (C) 2008 Nicolas Deram <nicolas@itaapy.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# Import from the Standard Library
import sys

# Import from itools
from itools.core import get_abspath, merge_dicts
from itools.datatypes import Email, String, Unicode
from itools.datatypes import Enumerate
from itools.gettext import MSG
from itools.stl import stl
from itools import vfs
from itools.web import STLView, INFO, ERROR
from itools.xapian import PhraseQuery, OrQuery, AndQuery, split_unicode

# Import from ikaaro
from config import get_config
from forms import AutoForm, SelectWidget, MultilineWidget, TextWidget
from views import SearchForm
from utils import get_base_path_query



class ForgottenPasswordForm(AutoForm):

    access = True
    title = MSG(u'Forgotten password')
    submit_value = MSG(u'Ok')

    widgets = [
        TextWidget('username', title=MSG(u'Type your email address')),
        ]

    schema = query_schema = {'username': Email(default='')}


    def get_value(self, resource, context, name, datatype):
        if name == 'username':
            return context.get_query_value('username')
        return AutoForm.get_value(self, resource, context, name, datatype)


    def action(self, resource, context, form):
        username = form['username']
        # TODO Don't generate the password, send instead a link to a form
        # where the user will be able to type his new password.
        root = context.root

        # Get the email address
        username = username.strip()

        # Get the user with the given login name
        results = root.search(username=username)
        if results.get_n_documents() == 0:
            message = ERROR(u'There is not a user identified as "{username}"',
                      username=username)
            context.message = message
            return

        user = results.get_documents()[0]
        user = resource.get_resource('/users/%s' % user.name)

        # Send email of confirmation
        email = user.get_property('email')
        user.send_forgotten_password(context, email)

        handler = resource.get_resource('/ui/website/forgotten_password.xml')
        return stl(handler)



class RegisterForm(AutoForm):

    access = 'is_allowed_to_register'
    title = MSG(u'Register')
    submit_value = MSG(u'Register')

    schema = {
        'firstname': Unicode(mandatory=True),
        'lastname': Unicode(mandatory=True),
        'email': Email(mandatory=True)}

    widgets = [
        TextWidget('firstname', title=MSG(u'First Name')),
        TextWidget('lastname', title=MSG(u'Last Name')),
        TextWidget('email', title=MSG(u'E-mail Address'))]


    def action(self, resource, context, form):
        # Get input data
        firstname = form['firstname'].strip()
        lastname = form['lastname'].strip()
        email = form['email'].strip()

        # Do we already have a user with that email?
        root = context.root
        user = root.get_user_from_login(email)
        if user is not None:
            if not user.has_property('user_must_confirm'):
                message = u'There is already an active user with that email.'
                context.message = ERROR(message)
                return
        else:
            # Add the user
            users = resource.get_resource('users')
            user = users.set_user(email, None)
            user.set_property('firstname', firstname)
            user.set_property('lastname', lastname)
            # Set the role
            default_role = resource.__roles__[0]['name']
            resource.set_user_role(user.name, default_role)

        # Send confirmation email
        user.send_confirmation(context, email)

        # Bring the user to the login form
        message = MSG(
            u"An email has been sent to you, to finish the registration "
            u"process follow the instructions detailed in it.")
        return message.gettext().encode('utf-8')



class ContactOptions(Enumerate):

    @classmethod
    def get_options(cls):
        resource = cls.resource
        users = resource.get_resource('/users')

        return [
            {'name': x, 'value': users.get_resource(x).get_title()}
            for x in resource.get_property('contacts') ]



class ContactForm(AutoForm):

    access = True
    title = MSG(u'Contact')
    submit_value = MSG(u'Send')
    query_schema = {'to': String,
                    'subject': Unicode,
                    'body': Unicode}

    def get_schema(self, resource, context):
        return {
            'to': ContactOptions(resource=resource, mandatory=True),
            'from': Email(mandatory=True),
            'subject': Unicode(mandatory=True),
            'body': Unicode(mandatory=True),
        }


    widgets = [
        SelectWidget('to', title=MSG(u'Recipient')),
        TextWidget('from', title=MSG(u'Your email address'), size=40),
        TextWidget('subject', title=MSG(u'Message subject'), size=40),
        MultilineWidget('body', title=MSG(u'Message body'), rows=8, cols=50),
    ]


    def get_value(self, resource, context, name, datatype):
        if name == 'from':
            user = context.user
            if user is not None:
                return user.get_property('email')
        else:
            query = context.query
            if name in query:
                return query[name]
        return datatype.get_default()


    def action(self, resource, context, form):
        # Get form values
        contact = form['to']
        from_addr = form['from'].strip()
        subject = form['subject'].strip()
        body = form['body'].strip()

        # Find out the "to" address
        contact = resource.get_resource('/users/%s' % contact)
        contact_title = contact.get_title()
        contact = contact.get_property('email')
        if contact_title != contact:
            contact = (contact_title, contact)
        # Send the email
        root = resource.get_root()
        root.send_email(contact, subject, from_addr=from_addr, text=body)
        # Ok
        context.message = INFO(u'Message sent.')



class SiteSearchView(SearchForm):

    access = True
    title = MSG(u'Search')
    template = '/ui/website/search.xml'

    search_schema = {
        'site_search_text': Unicode,
    }


    def get_namespace(self, resource, context):
        namespace = SearchForm.get_namespace(self, resource, context)
        namespace['text'] = context.query['site_search_text'].strip()
        return namespace


    def get_query_schema(self):
        schema = merge_dicts(SearchForm.get_query_schema(self))
        del schema['sort_by']
        del schema['reverse']
        return schema


    def get_search_namespace(self, resource, context):
        text = context.query['site_search_text']
        return {'text': text}


    search_template = '/ui/website/search_form.xml'
    def get_items(self, resource, context):
        text = context.query['site_search_text'].strip()
        if not text:
            return []

        # The Search Query
        languages = resource.get_property('website_languages')
        queries = []
        for language in languages:
            query = [ OrQuery(PhraseQuery('title', word),
                              PhraseQuery('text', word))
                      for word in split_unicode(text, language) ]
            if query:
                queries.append(AndQuery(*query))

        if not queries:
            return []
        query = OrQuery(*queries)

        # Search
        abspath = resource.get_canonical_path()
        q1= get_base_path_query(str(abspath))
        query = AndQuery(q1, query)
        root = context.root
        results = root.search(query=query)
        documents = results.get_documents()

        # Check access rights
        user = context.user
        items = []
        for document in documents:
            child = root.get_resource(document.abspath)
            ac = child.get_access_control()
            if ac.is_allowed_to_view(user, child):
                items.append(child)

        return items


    def sort_and_batch(self, resource, context, items):
        # Batch
        start = context.query['batch_start']
        size = context.query['batch_size']
        return items[start:start+size]


    table_template = '/ui/website/search_table.xml'
    def get_table_namespace(self, resource, context, items):
        # Build the namespace
        site_root = resource.get_site_root()
        items_ns = [{
            'abspath': '/%s' % site_root.get_pathto(item),
            'title': item.get_title(),
            'type': item.class_title.gettext(),
            'size': item.get_human_size(),
            'url': '%s/' % resource.get_pathto(item),
            'icon': item.get_class_icon(),
        } for item in items ]

        return {'items': items_ns}



class AboutView(STLView):

    access = True
    title = MSG(u'About')
    template = '/ui/root/about.xml'


    def get_namespace(self, resource, context):
        # Python, itools & ikaaro
        packages = ['sys', 'itools', 'ikaaro']
        config = get_config(context.server.target)
        packages.extend(config.get_value('modules'))
        # Try packages we frequently use
        packages.extend([
            'gio', 'xapian', 'pywin32', 'PIL.Image', 'docutils', 'reportlab',
            'xlrd'])
        # Mapping from package to version attribute
        package2version = {
            'gio': 'pygio_version',
            'xapian': 'version_string',
            'PIL.Image': 'VERSION',
            'reportlab': 'Version',
            'sys': 'version_info',
            'xlrd': '__VERSION__'}
        package2title = {
            'gio': 'pygobject',
            'sys': 'Python',
            }

        # Namespace
        packages_ns = []
        for name in packages:
            attribute = package2version.get(name, '__version__')
            # Import
            if '.' in name:
                name, subname = name.split('.')
                try:
                    package = __import__(subname, fromlist=[name])
                except ImportError:
                    continue
            else:
                try:
                    package = __import__(name)
                except ImportError:
                    continue

            # Version
            try:
                version = getattr(package, attribute)
            except AttributeError:
                version = MSG(u'no version found')
            else:
                if hasattr(version, '__call__'):
                    version = version()
                if isinstance(version, tuple):
                    version = '.'.join([str(v) for v in version])
            # Ok
            title = package2title.get(name, name)
            packages_ns.append({'name': title, 'version': version})

        # Insert first the platform
        platform = {
            'linux2': 'GNU/Linux',
            'darwin': 'Mac OS X',
            'win32': 'Windows'}.get(sys.platform, sys.platform)
        packages_ns.insert(0,
            {'name': MSG(u'Operating System'), 'version': platform})

        namespace = {'packages': packages_ns}
        return namespace



class CreditsView(STLView):

    access = True
    title = MSG(u'Credits')
    template = '/ui/root/credits.xml'


    def get_namespace(self, resource, context):
        context.styles.append('/ui/credits.css')

        # Build the namespace
        credits = get_abspath('CREDITS')
        lines = vfs.open(credits).readlines()
        names = [ x[3:].strip() for x in lines if x.startswith('N: ') ]

        return {'hackers': names}

