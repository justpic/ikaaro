# -*- coding: UTF-8 -*-
# Copyright (C) 2006-2007 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2006-2007 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2007 Nicolas Deram <nicolas@itaapy.com>
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
from datetime import datetime

# Import from itools
from itools.datatypes import DateTime, FileName, String
from itools.handlers import File
from itools.html import (XHTMLFile, sanitize_stream, HTMLParser,
    stream_to_str_as_xhtml)
from itools.stl import stl
from itools.xml import TEXT, START_ELEMENT, XMLError

# Import from ikaaro
from messages import *
from multilingual import Multilingual
from text import Text
from registry import register_object_class


class EpozEditable(object):
    """A mixin class for handlers implementing HTML editing.
    """

    #######################################################################
    # API
    #######################################################################
    def get_epoz_document(self):
        # Implement it in your editable handler
        raise NotImplementedError


    def get_epoz_data(self):
        document = self.get_epoz_document()
        body = document.get_body()
        if body is None:
            return None
        return body.get_content_elements()


    #######################################################################
    # User Interface
    #######################################################################
    edit_form__access__ = 'is_allowed_to_edit'
    edit_form__label__ = u'Edit'
    edit_form__sublabel__ = u'Inline'
    def edit_form(self, context):
        """WYSIWYG editor for HTML documents.
        """
        data = self.get_epoz_data()
        # If the document has not a body (e.g. a frameset), edit as plain text
        if data is None:
            return Text.edit_form(self, context)

        # Edit with a rich text editor
        namespace = {}
        namespace['timestamp'] = DateTime.encode(datetime.now())
        namespace['rte'] = self.get_rte(context, 'data', data)

        handler = self.get_object('/ui/html/edit.xml')
        return stl(handler, namespace)


    edit__access__ = 'is_allowed_to_edit'
    def edit(self, context, sanitize=False):
        timestamp = context.get_form_value('timestamp', type=DateTime)
        if timestamp is None:
            return context.come_back(MSG_EDIT_CONFLICT)
        document = self.get_epoz_document()
        if document.timestamp is not None and timestamp < document.timestamp:
            return context.come_back(MSG_EDIT_CONFLICT)

        # Sanitize
        new_body = context.get_form_value('data')
        try:
            new_body = HTMLParser(new_body)
        except XMLError:
            return context.come_back(u'Invalid HTML code.')
        if sanitize:
            new_body = sanitize_stream(new_body)
        # "get_epoz_document" is to set in your editable handler
        old_body = document.get_body()
        events = (document.events[:old_body.start+1] + new_body
                  + document.events[old_body.end:])
        # Change
        document.set_events(events)
        context.server.change_object(self)

        return context.come_back(MSG_CHANGES_SAVED)



class WebPage(EpozEditable, Multilingual, Text):

    class_id = 'webpage'
    class_version = '20071216'
    class_title = u'Web Page'
    class_description = u'Create and publish a Web Page.'
    class_icon16 = 'images/HTML16.png'
    class_icon48 = 'images/HTML48.png'
    class_views = [['view'],
                   ['edit_form', 'externaledit', 'upload_form'],
                   ['edit_metadata_form'],
                   ['state_form'],
                   ['history_form']]
    class_handler = XHTMLFile


    @classmethod
    def get_metadata_schema(cls):
        schema = Text.get_metadata_schema()
        # FIXME Needed by the upgrade code from 0.16 to 0.20
        schema['language'] = String
        return schema


    #######################################################################
    # API
    #######################################################################
    def to_text(self):
        text = [ x.to_text() for x in self.get_handlers() ]
        return ' '.join(text)


    GET__mtime__ = None
    def GET(self, context):
        method = self.get_firstview()
        # Check access
        if method is None:
            raise Forbidden
        # Redirect
        return context.uri.resolve2(';%s' % method)


    def is_empty(self):
        """Test if XML doc is empty
        """
        body = self.get_body()
        if body is None:
            return True
        for type, value, line in body.events:
            if type == TEXT:
                if value.replace('&nbsp;', '').strip():
                    return False
            elif type == START_ELEMENT:
                tag_uri, tag_name, attributes = value
                if tag_name == 'img':
                    return False
        return True


    def get_content_type(self):
        return 'application/xhtml+xml; charset=UTF-8'


    #######################################################################
    # UI / View
    #######################################################################
    view__access__ = 'is_allowed_to_view'
    view__label__ = u'View'
    view__title__ = u'View'
    def view(self, context):
        namespace = {}
        body = self.handler.get_body()
        if body is None:
            namespace['text'] = None
        else:
            namespace['text'] = body.get_content_elements()

        handler = self.get_object('/ui/html/view.xml')
        return stl(handler, namespace)


    #######################################################################
    # UI / Edit / Inline
    #######################################################################
    def get_epoz_document(self):
        return self.handler


    #######################################################################
    # Update
    #######################################################################
    def update_20071215(self):
        remove = ['id', 'owner', 'ikaaro:history', 'ikaaro:wf_transition',
                  'ikaaro:user_theme']
        rename = [('dc:language', 'language')]
        Text.update_20071215(self, remove=remove, rename=rename)


    def update_20071216(self):
        """Merge metadata files of multilingual objects:

          Before                       After
          -----------------------      --------------
          index.xhtml.en.metadata      index.metadata
          index.xhtml.en               index.xhtml.en
          index.xhtml.fr.metadata      index.xhtml.fr
          index.xhtml.fr

        Add missing language extension to multilingual handlers when missing:

          Before                       After
          -----------------------      --------------
          index.xhtml.metadata         index.metadata
          index.xhtml                  index.xhtml.en

        """
        # Possible message errors
        error1 = '%s: unexpected value of type list for property "%s"'
        error2 = '%s: metadata merge failed, value conflict for property "%s"'

        # Skip anything else that is not a WebPage
        format = self.metadata.format
        is_xhtml = (format == 'application/xhtml+xml')
        is_html = (format == 'text/html')

        # Web Pages
        container = self.parent.handler
        old_meta = self.metadata
        name = self.name
        # HTML => XHTML
        if is_html:
            handler = container.get_handler(name, cls=File, cache=False)
            data = stream_to_str_as_xhtml(HTMLParser(handler.data))
            handler = File(string=data)
        # No language, like "index.xhtml"
        main, extension, lang = FileName.decode(name)
        if lang is None:
            # Add the language suffix
            lang = old_meta.get_property('language')
            if lang is None:
                lang = self.get_site_root().get_default_language()
            # Rename handler
            new_name = FileName.encode((main, 'xhtml', lang))
            if is_html:
                container.del_handler(name)
                container.set_handler(new_name, handler)
            elif container.has_handler(name):
                # Be robust against wrong extensions
                container.get_handler(name, cls=self.class_handler)
                container.move_handler(name, new_name)
            # Rename metadata
            old_name = '%s.metadata' % name
            new_name = '%s.metadata' % main
            container.move_handler(old_name, new_name)
            if is_html or is_xhtml:
                old_meta.format = 'webpage'
            return

        # With language, like "index.xhtml.en"
        new_name = main
        new_name = '%s.metadata' % new_name
        if container.has_handler(new_name):
            # Merge metadata
            new_meta = container.get_handler(new_name)
            for pname, pvalue in old_meta.properties.items():
                if pname == 'language':
                    continue
                ptype = type(pvalue)
                if ptype is list:
                    raise TypeError, error1 % (self.abspath, pname)
                elif ptype is dict:
                    value = old_meta.get_property(pname, lang)
                    if value.strip():
                        new_meta.set_property(pname, value, lang)
                elif pvalue != new_meta.get_property(pname):
                    raise ValueError, error2 % (self.abspath, pname)
        else:
            # Metadata
            new_meta = old_meta.clone()
            if is_html or is_xhtml:
                new_meta.format = 'webpage'
            new_meta.del_property('language')
            container.set_handler(new_name, new_meta)
        container.del_handler('%s.metadata' % name)
        # HTML => XHTML
        if is_html:
            container.del_handler(name)
            new_name = FileName.encode((main, 'xhtml', lang))
            container.set_handler(new_name, handler)
        # Switch metadata
        self.metadata = new_meta



###########################################################################
# Register
###########################################################################
register_object_class(WebPage)
register_object_class(WebPage, format='text/html')
register_object_class(WebPage, format='application/xhtml+xml')
