'''
finger_pks.py

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
import core.controllers.output_manager as om
import core.data.kb.knowledge_base as kb
import core.data.kb.info as info

from core.controllers.plugins.infrastructure_plugin import InfrastructurePlugin
from core.controllers.exceptions import w3afRunOnce
from core.controllers.misc.decorators import runonce
from core.data.search_engines.pks import pks as pks
from core.data.parsers.url import URL


class finger_pks(InfrastructurePlugin):
    '''
    Search MIT PKS to get a list of users for a domain.
    @author: Andres Riancho (andres.riancho@gmail.com)
    '''

    def __init__(self):
        InfrastructurePlugin.__init__(self)

    @runonce(exc_class=w3afRunOnce)
    def discover(self, fuzzable_request):
        '''
        @param fuzzable_request: A fuzzable_request instance that contains
                                    (among other things) the URL to test.
        '''
        root_domain = fuzzable_request.get_url().get_root_domain()

        pks_se = pks(self._uri_opener)
        results = pks_se.search(root_domain)

        for result in results:
            i = info.info()
            i.set_url(URL('http://pgp.mit.edu:11371/'))
            i.set_plugin_name(self.get_name())
            i.set_id([])
            mail = result.username + '@' + root_domain
            i.set_name(mail)
            i.set_desc('The mail account: "' + mail +
                       '" was found in the MIT PKS server. ')
            i['mail'] = mail
            i['user'] = result.username
            i['name'] = result.name
            i['url_list'] = ['http://pgp.mit.edu:11371/', ]
            kb.kb.append('emails', 'emails', i)
            #   Don't save duplicated information in the KB. It's useless.
            #kb.kb.append( self, 'emails', i )
            om.out.information(i.get_desc())

    def get_long_desc(self):
        '''
        @return: A DETAILED description of the plugin functions and features.
        '''
        return '''
        This plugin finds mail addresses in PGP PKS servers.
        '''
