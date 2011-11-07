# -*- coding: UTF-8 -*-
# Copyright (C) 2005-2008 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2006-2007 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2007 Henry Obein <henry@itaapy.com>
# Copyright (C) 2007-2008 Sylvain Taverne <sylvain@itaapy.com>
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

# Import from itools
from itools.database import register_field
from itools.datatypes import String
from itools.gettext import MSG
from itools.web import INFO

# Import from ikaaro
from autoedit import AutoEdit
from autoform import CheckboxWidget
from datatypes import UserGroups_Datatype
from fields import Char_Field, Email_Field, Password_Field, Text_Field
from fields import File_Field, Select_Field, URI_Field
from folder import Folder
from resource_ import DBResource
from user_views import User_ConfirmRegistration, User_EditAccount
from user_views import User_EditPassword, User_EditPreferences, User_Profile
from user_views import User_ResendConfirmation
from user_views import User_ChangePasswordForgotten, UserFolder_BrowseContent
from utils import get_secure_hash, generate_password
from views import MessageView


class UserGroups_Field(URI_Field):

    datatype = UserGroups_Datatype
    indexed = True
    multiple = True
    title = MSG(u'Groups')
    widget = CheckboxWidget



class UserState_Field(Select_Field):

    parameters_schema = {'key': String}
    default = 'active'
    options = [
        {'name': 'active', 'value': MSG(u'Active')},
        {'name': 'pending', 'value': MSG(u'Pending confirmation')},
        {'name': 'inactive', 'value': MSG(u'Inactive')}]



class User(DBResource):

    class_id = 'user'
    class_version = '20081217'
    class_title = MSG(u'User')
    class_icon16 = 'icons/16x16/user.png'
    class_icon48 = 'icons/48x48/user.png'
    class_views = ['profile', 'edit_account', 'edit_preferences',
                   'edit_password', 'edit_groups']


    # Fields
    firstname = Text_Field(multilingual=False, indexed=True, stored=True,
                           title=MSG(u'First Name'))
    lastname = Text_Field(multilingual=False, indexed=True, stored=True,
                          title=MSG(u'Last Name'))
    email = Email_Field(indexed=True, stored=True, required=True,
                        unique=True, title=MSG(u'E-mail Address'))
    password = Password_Field
    avatar = File_Field(title=MSG(u'Avatar'))
    user_language = Char_Field
    user_timezone = Char_Field
    user_state = UserState_Field
    groups = UserGroups_Field
    username = Char_Field(indexed=True, stored=True) # Backwards compatibility

    # Remove some fields
    title = None
    description = None
    subject = None
    text = None


    ########################################################################
    # Indexing
    ########################################################################
    def get_catalog_values(self):
        values = super(User, self).get_catalog_values()

        # email domain
        email = self.get_value('email')
        if email and '@' in email:
            values['email_domain'] = email.split('@', 1)[1]

        # username (overrides default)
        values['username'] = self.get_login_name()

        # groups
        values['groups'] = self.get_value('groups')

        return values


    ########################################################################
    # API / Authentication
    ########################################################################
    def get_user_id(self):
        # Used by itools.web
        return str(self.name)


    def get_auth_token(self):
        # Used by itools.web
        return self.get_value('password')


    def authenticate(self, password):
        secure_hash = get_secure_hash(password)
        return secure_hash == self.get_value('password')


    def login(self, context):
        context.login(self)
        # To activte this feature set the lastlog field
        lastlog = self.get_field('lastlog')
        if lastlog:
            self.set_value('lastlog', context.timestamp)


    def update_pending_key(self):
        state = self.get_property('user_state')
        if state.value == 'pending':
            # TODO Implement expiration
            return state.get_parameter('key')

        key = generate_password(30)
        self.set_value('user_state', 'pending', key=key)
        return key


    ########################################################################
    # API
    ########################################################################
    def get_owner(self):
        return str(self.abspath)


    def get_title(self, language=None):
        firstname = self.get_value('firstname')
        lastname = self.get_value('lastname')
        if firstname:
            if lastname:
                return '%s %s' % (firstname, lastname)
            return firstname
        if lastname:
            return lastname
        return self.get_login_name().decode('utf-8')


    login_name_property = 'email'
    def get_login_name(self):
        return self.get_value(self.login_name_property)


    def get_timezone(self):
        return self.get_value('user_timezone')


    def account_is_completed(self):
        for name, field in self.get_fields():
            if field.required and self.get_value(name) is None:
                return False
        return True


    #######################################################################
    # Views
    #######################################################################
    resend_confirmation = User_ResendConfirmation
    confirm_registration = User_ConfirmRegistration
    change_password_forgotten = User_ChangePasswordForgotten
    profile = User_Profile
    edit_account = User_EditAccount
    edit_preferences = User_EditPreferences
    edit_password = User_EditPassword
    edit_groups = AutoEdit(access='is_admin', fields=['groups'],
                           title=MSG(u'Edit groups'))



class UserFolder(Folder):

    class_id = 'users'
    class_title = MSG(u'User Folder')
    class_icon16 = 'icons/16x16/userfolder.png'
    class_icon48 = 'icons/48x48/userfolder.png'
    class_views = ['view', 'browse_content', 'edit']
    is_content = False


    def get_document_types(self):
        return [self.database.get_resource_class('user')]


    #######################################################################
    # API
    #######################################################################
    def get_usernames(self):
        """Return all user names."""
        names = self._get_names()
        return frozenset(names)


    #######################################################################
    # Back-Office
    #######################################################################
    browse_content = UserFolder_BrowseContent()
    edit = AutoEdit(access='is_admin')


    #######################################################################
    # View
    view = MessageView(
        access='is_admin',
        title=MSG(u'View'),
        icon='view.png',
        message=INFO(u'To manage the users please go '
                     u'<a href="/config/users">here</a>.'))


# Register
register_field('email_domain', String(indexed=True, stored=True))
