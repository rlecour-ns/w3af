'''
strange_http_codes.py

Copyright 2006 Andres Riancho

This file is part of w3af, w3af.sourceforge.net .

w3af is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation version 2 of the License.

w3af is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with w3af; if not, write to the Free Software
Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

'''
import core.data.kb.knowledge_base as kb
import core.data.kb.info as info

from core.controllers.plugins.grep_plugin import GrepPlugin


class strange_http_codes(GrepPlugin):
    '''
    Analyze HTTP response codes sent by the remote web application.

    @author: Andres Riancho (andres.riancho@gmail.com)
    '''

    COMMON_HTTP_CODES = set([200,
                             301, 302, 303, 304,
                             401, 403, 404,
                             500, 501])

    def __init__(self):
        GrepPlugin.__init__(self)

    def grep(self, request, response):
        '''
        Plugin entry point. Analyze if the HTTP response codes are strange.

        @param request: The HTTP request object.
        @param response: The HTTP response object
        @return: None, all results are saved in the kb.
        '''
        if response.get_code() not in self.COMMON_HTTP_CODES:

            # I check if the kb already has a info object with this code:
            strange_code_infos = kb.kb.get(
                'strange_http_codes', 'strange_http_codes')

            corresponding_info = None
            for info_obj in strange_code_infos:
                if info_obj['code'] == response.get_code():
                    corresponding_info = info_obj
                    break

            if corresponding_info:
                # Work with the "old" info object:
                id_list = corresponding_info.get_id()
                id_list.append(response.id)
                corresponding_info.set_id(id_list)

            else:
                # Create a new info object from scratch and save it to the kb:
                i = info.info()
                i.set_plugin_name(self.get_name())
                i.set_name(
                    'Strange HTTP Response code - ' + str(response.get_code()))
                i.set_url(response.get_url())
                i.set_id(response.id)
                i['code'] = response.get_code()
                desc = 'The remote Web server sent a strange HTTP response code: "'
                desc += str(response.get_code(
                )) + '" with the message: "' + response.get_msg()
                desc += '", manual inspection is advised.'
                i.set_desc(desc)
                i.add_to_highlight(str(response.get_code()), response.get_msg())
                kb.kb.append(self, 'strange_http_codes', i)

    def end(self):
        '''
        This method is called when the plugin wont be used anymore.
        '''
        self.print_uniq(
            kb.kb.get('strange_http_codes', 'strange_http_codes'), 'URL')

    def get_long_desc(self):
        '''
        @return: A DETAILED description of the plugin functions and features.
        '''
        return '''
        Analyze HTTP response codes sent by the remote web application and
        report uncommon findings.
        '''
