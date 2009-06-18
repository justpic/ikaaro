# -*- coding: UTF-8 -*-
# Copyright (C) 2009 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2009 Hervé Cauwelier <herve@itaapy.com>
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
from datetime import date

# Import from itools
from itools.core import freeze
from itools.csv import Property
from itools.datatypes import Date, Enumerate, String, Unicode
from itools.gettext import MSG

# Import from ikaaro
from ikaaro.file import File
from ikaaro.folder import Folder
from ikaaro.forms import AutoForm, DateWidget, SelectWidget, TextWidget
from ikaaro.forms import description_widget, title_widget
from ikaaro import messages
from ikaaro.registry import register_resource_class, register_document_type
from ikaaro.views_new import NewInstance


# FIXME dtstart and dtend must be datetime objects, the problem is we do
# not have the DateTimeWidget yet.


class TodayDataType(Date):

    @classmethod
    def get_default(cls):
        return date.today()



class Status(Enumerate):

    options = [
        {'name': 'TENTATIVE', 'value': MSG(u'Tentative')},
        {'name': 'CONFIRMED', 'value': MSG(u'Confirmed')},
        {'name': 'CANCELLED', 'value': MSG(u'Cancelled')}]




class Event_NewInstance(NewInstance):

    query_schema = freeze({
        'type': String,
        'title': Unicode,
        'dtstart': TodayDataType,
        'dtend': TodayDataType,
        'description': Unicode,
        'location': String,
        'status': Status})

    schema = freeze({
        'title': Unicode(mandatory=True),
        'dtstart': TodayDataType(mandatory=True),
        'dtend': TodayDataType,
        'description': Unicode,
        'location': String,
        'status': Status})

    widgets = freeze([
        title_widget,
        DateWidget('dtstart', title=MSG(u'Start')),
        DateWidget('dtend', title=MSG(u'End')),
        description_widget,
        TextWidget('location', title=MSG(u'Location')),
        SelectWidget('status', title=MSG(u'Status'), has_empty_option=False)])


    def get_schema(self, resource, context):
        return self.schema


    def get_new_resource_name(self, form):
        return form['title'].strip()


    def action(self, resource, context, form):
        dtstart = form['dtstart']

        # Get the container, create it if needed
        container = context.site_root
        names = [
            '%04d' % dtstart.year,
            '%02d' % dtstart.month,
            '%02d' % dtstart.day]
        for name in names:
            folder = container.get_resource(name, soft=True)
            if folder is None:
                folder = Folder.make_resource(Folder, container, name)
            container = folder

        # Make the event
        event_name = form['name']
        event = Event.make_resource(Event, container, event_name)
        # The metadata
        language = resource.get_content_language(context)
        for name in 'title', 'description':
            property = Property(form[name], lang=language)
            event.metadata.set_property(name, property)
        for name in 'dtstart', 'dtend', 'location', 'status':
            event.metadata.set_property(name, form[name])

        # Ok
        goto = '%s/%s/' % (container.get_abspath(), event_name)
        return context.come_back(messages.MSG_NEW_RESOURCE, goto=goto)



class Event_Edit(AutoForm):

    access = 'is_allowed_to_edit'
    title = MSG(u'Edit event')


    schema = freeze({
        'title': Unicode(mandatory=True),
        'dtstart': TodayDataType(mandatory=True),
        'dtend': TodayDataType,
        'description': Unicode,
        'location': String,
        'status': Status})

    widgets = freeze([
        title_widget,
        DateWidget('dtstart', title=MSG(u'Start')),
        DateWidget('dtend', title=MSG(u'End')),
        description_widget,
        TextWidget('location', title=MSG(u'Location')),
        SelectWidget('status', title=MSG(u'Status'), has_empty_option=False)])


    def get_value(self, resource, context, name, datatype):
        return resource.get_property(name)


    def _get_form(self, resource, context):
        """ Check start is before end.
        """
        form = AutoForm._get_form(self, resource, context)
        start_date = form['dtstart']
        start_time = form.get('dtstart_time', None) or time(0,0)
        end_date = form['dtend']
        end_time = form.get('dtend_time', None) or time(23,59)
        start = datetime.combine(start_date, start_time)
        end = datetime.combine(end_date, end_time)

        if start > end:
            msg = ERROR(u'Invalid dates.')
            raise FormError(msg)
        return form


    def action(self, resource, context, form):
        # The metadata
        language = resource.get_content_language(context)
        for name in 'title', 'description':
            property = Property(form[name], lang=language)
            resource.set_property(name, property)
        for name in 'dtstart', 'dtend', 'location', 'status':
            resource.set_property(name, form[name])



class Event(File):

    class_id = 'event'
    class_title = MSG(u'Event')
    class_description = MSG(u'...')
    class_icon16 = 'icons/16x16/icalendar.png'
    class_icon48 = 'icons/48x48/icalendar.png'
    class_views = ['edit', 'backlinks', 'edit_state']


    @classmethod
    def get_metadata_schema(cls):
        schema = File.get_metadata_schema()
        schema['dtstart'] = Date
        schema['dtend'] = Date
        schema['status'] = Status
        schema['location'] = String
        return schema


    def _get_catalog_values(self):
        values = File._get_catalog_values(self)
        values['dtstart'] = self.get_property('dtstart')
        values['dtend'] = self.get_property('dtend')
        return values


    # Views
    new_instance = Event_NewInstance()
    edit = Event_Edit()



# Register
register_resource_class(Event)
register_document_type(Event)
