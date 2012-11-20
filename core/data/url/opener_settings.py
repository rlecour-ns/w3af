'''
opener_settings.py

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
import urllib2
import socket
import urlparse
import cookielib

import core.controllers.output_manager as om
import core.data.url.handlers.HTTPNtlmAuthHandler as HTTPNtlmAuthHandler
import core.data.url.handlers.MultipartPostHandler as MultipartPostHandler
import core.data.url.handlers.localCache as localCache
import core.data.url.handlers.mangleHandler as mangleHandler

from core.controllers.configurable import Configurable
from core.controllers.exceptions import w3afException
from core.data.kb.config import cf as cfg
from core.data.options.opt_factory import opt_factory
from core.data.options.option_list import OptionList
from core.data.parsers.url import URL
from core.data.url.handlers.FastHTTPBasicAuthHandler import FastHTTPBasicAuthHandler
from core.data.url.handlers.cookie_handler import CookieHandler
from core.data.url.handlers.gzip_handler import HTTPGzipProcessor
from core.data.url.handlers.keepalive import HTTPHandler as kAHTTP
from core.data.url.handlers.keepalive import HTTPSHandler as kAHTTPS
from core.data.url.handlers.logHandler import LogHandler
from core.data.url.handlers.redirect import HTTPErrorHandler, HTTP30XHandler
from core.data.url.handlers.urlParameterHandler import URLParameterHandler


class OpenerSettings(Configurable):
    '''
    This is a urllib2 configuration manager.

    @author: Andres Riancho (andres.riancho@gmail.com)
    '''
    def __init__(self):

        # Set the openers to None
        self._basicAuthHandler = None
        self._proxyHandler = None
        self._httpsHandler = None
        self._mangleHandler = None
        self._urlParameterHandler = None
        self._ntlmAuthHandler = None
        # Keep alive handlers are created on build_openers()

        cj = cookielib.MozillaCookieJar()
        self._cookieHandler = CookieHandler(cj)

        # Openers
        self._uri_opener = None

        # Some internal variables
        self.need_update = True

        #
        #    I've found some websites that check the user-agent string, and
        #    don't allow you to access if you don't have IE (mostly ASP.NET
        #    applications do this). So now we use the following user-agent
        #    string in w3af:
        #
        user_agent = 'Mozilla/4.0 (compatible; MSIE 8.0; Windows NT 6.1; Trident/4.0;'
        user_agent += ' w3af.sf.net)'
        #   which basically is the UA for IE8 running in Windows 7, plus our website :)
        self.header_list = [('User-Agent', user_agent)]

        # By default, dont mangle any request/responses
        self._manglePlugins = []

        # User configured variables
        if cfg.get('timeout') is None:
            # This is the first time we are executed...

            cfg.save('timeout', 15)
            socket.setdefaulttimeout(cfg.get('timeout'))
            cfg.save('headersFile', '')
            cfg.save('cookieJarFile', '')
            cfg.save('User-Agent', 'w3af.sourceforge.net')

            cfg.save('proxyAddress', '')
            cfg.save('proxyPort', 8080)

            cfg.save('basicAuthPass', '')
            cfg.save('basicAuthUser', '')
            cfg.save('basicAuthDomain', '')

            cfg.save('ntlmAuthDomain', '')
            cfg.save('ntlmAuthUser', '')
            cfg.save('ntlmAuthPass', '')
            cfg.save('ntlmAuthURL', '')

            cfg.save('ignoreSessCookies', False)
            cfg.save('maxFileSize', 400000)
            cfg.save('maxRetrys', 2)

            cfg.save('urlParameter', '')

            # 404 settings
            cfg.save('never404', [])
            cfg.save('always404', [])
            cfg.save('404string', '')

    def set_headersFile(self, headers_file):
        '''
        Sets the special headers to use, this headers are specified in a file by the user.
        The file can have multiple lines, each line should have the following structure :
            - HEADER:VALUE_OF_HEADER

        @param headers_file: The filename where the special headers are specified.
        @return: No value is returned.
        '''
        om.out.debug('Called SetHeaders()')
        if headers_file != '':
            try:
                f = open(headers_file, 'r')
            except:
                raise w3afException(
                    'Unable to open headers file: ' + headers_file)

            hList = []
            for line in f:
                header_name = line.split(':')[0]
                header_value = ':'.join(line.split(':')[1:])
                header_value = header_value.strip()
                hList.append((header_name, header_value))

            self.set_header_list(hList)
            cfg.save('headersFile', headers_file)

    def set_header_list(self, hList):
        '''
        @param hList: A list of tuples with (header,value) to be added to every request.
        @return: nothing
        '''
        for h, v in hList:
            self.header_list.append((h, v))
            om.out.debug('Added the following header: ' + h + ': ' + v)

    def getheaders_file(self):
        return cfg.get('headersFile')

    def set_cookieJarFile(self, CookieJarFile):
        om.out.debug('Called SetCookie')

        if CookieJarFile != '':
            cj = cookielib.MozillaCookieJar()
            try:
                cj.load(CookieJarFile)
            except Exception, e:
                raise w3afException('Error while loading cookiejar file. Description: ' + str(e))

            self._cookieHandler = CookieHandler(cj)
            cfg.save('cookieJarFile', CookieJarFile)

    def get_cookieJarFile(self):
        return cfg.get('cookieJarFile')

    def get_cookies(self):
        '''
        @return: The cookies that were collected during this scan.
        '''
        return self._cookieHandler.cookiejar

    def set_timeout(self, timeout):
        om.out.debug('Called SetTimeout(' + str(timeout) + ')')
        if timeout > 60 or timeout < 1:
            raise w3afException(
                'The timeout parameter should be between 1 and 60 seconds.')
        else:
            cfg.save('timeout', timeout)

            # Set the default timeout
            # I dont need to use timeoutsocket.py , it has been added to python sockets
            socket.setdefaulttimeout(cfg.get('timeout'))

    def get_timeout(self):
        return cfg.get('timeout')

    def set_user_agent(self, useragent):
        om.out.debug('Called SetUserAgent')
        self.header_list = [i for i in self.header_list if i[0]
                            != 'User-Agent']
        self.header_list.append(('User-Agent', useragent))
        cfg.save('User-Agent', useragent)

    def get_user_agent(self):
        return cfg.get('User-Agent')

    def set_proxy(self, ip, port):
        '''
        Saves the proxy information and creates the handler.

        If the information is invalid it will set self._proxyHandler to None,
        so no proxy is used.

        @return: None
        '''
        om.out.debug('Called set_proxy(%s,%s)' % (ip, port))

        if not ip:
            #    The user doesn't want a proxy anymore
            cfg.save('proxyAddress', '')
            cfg.save('proxyPort', '')
            self._proxyHandler = None
            return

        if port > 65535 or port < 1:
            #    The user entered something invalid
            self._proxyHandler = None
            raise w3afException('Invalid port number: ' + str(port))

        #
        #    Great, we have all valid information.
        #
        cfg.save('proxyAddress', ip)
        cfg.save('proxyPort', port)

        #
        #    Remember that this line:
        #
        #proxyMap = { 'http' : "http://" + ip + ":" + str(port) , 'https' : "https://" + ip + ":" + str(port) }
        #
        #    makes no sense, because urllib2.ProxyHandler doesn't support HTTPS proxies with CONNECT.
        #    The proxying with CONNECT is implemented in keep-alive handler. (nasty!)
        proxyMap = {'http': "http://" + ip + ":" + str(port)}
        self._proxyHandler = urllib2.ProxyHandler(proxyMap)

    def get_proxy(self):
        return cfg.get('proxyAddress') + ':' + str(cfg.get('proxyPort'))

    def set_basic_auth(self, url, username, password):
        om.out.debug('Called SetBasicAuth')

        if not url:
            if url is None:
                raise w3afException(
                    'The entered basicAuthDomain URL is invalid!')
            elif username or password:
                msg = ('To properly configure the basic authentication '
                       'settings, you should also set the auth domain. If you '
                       'are unsure, you can set it to the target domain name.')
                raise w3afException(msg)
        else:
            if not hasattr(self, '_password_mgr'):
                # Create a new password manager
                self._password_mgr = urllib2.HTTPPasswordMgrWithDefaultRealm()

            # Add the username and password
            domain = url.get_domain()
            protocol = url.get_protocol()
            protocol = protocol if protocol in ('http', 'https') else 'http'
            self._password_mgr.add_password(None, domain, username, password)
            self._basicAuthHandler = FastHTTPBasicAuthHandler(
                self._password_mgr)

            # Only for w3af, no usage in urllib2
            self._basicAuthStr = protocol + '://' + username + \
                ':' + password + '@' + domain + '/'
            self.need_update = True

        # Save'em!
        cfg.save('basicAuthPass', password)
        cfg.save('basicAuthUser', username)
        cfg.save('basicAuthDomain', url)

    def get_basic_auth(self):
        scheme, domain, path, x1, x2, x3 = urlparse.urlparse(
            cfg.get('basicAuthDomain'))
        res = scheme + '://' + cfg.get('basicAuthUser') + ':'
        res += cfg.get('basicAuthPass') + '@' + domain + '/'
        return res

    def set_ntlm_auth(self, url, ntlm_domain, username, password):

        cfg.save('ntlmAuthPass', password)
        cfg.save('ntlmAuthDomain', ntlm_domain)
        cfg.save('ntlmAuthUser', username)
        cfg.save('ntlmAuthURL', url)

        om.out.debug('Called SetNtlmAuth')

        if not hasattr(self, '_password_mgr'):
            # create a new password manager
            self._password_mgr = urllib2.HTTPPasswordMgrWithDefaultRealm()

        # HTTPNtmlAuthHandler expects username to have the domain name
        # separated with a '\', so that's what we do here:
        username = ntlm_domain + '\\' + username

        self._password_mgr.add_password(None, url, username, password)
        self._ntlmAuthHandler = HTTPNtlmAuthHandler.HTTPNtlmAuthHandler(
            self._password_mgr)

        self.need_update = True

    def build_openers(self):
        om.out.debug('Called build_openers')

        # Instantiate the handlers passing the proxy as parameter
        self._kAHTTP = kAHTTP()
        self._kAHTTPS = kAHTTPS(self.get_proxy())
        self._cache_hdler = localCache.CacheHandler()

        # Prepare the list of handlers
        handlers = []
        for handler in [self._proxyHandler, self._basicAuthHandler,
                        self._ntlmAuthHandler, self._cookieHandler,
                        MultipartPostHandler.MultipartPostHandler,
                        self._kAHTTP, self._kAHTTPS, LogHandler,
                        HTTPErrorHandler, HTTP30XHandler,
                        mangleHandler.mangleHandler(self._manglePlugins),
                        HTTPGzipProcessor, self._urlParameterHandler,
                        self._cache_hdler]:
            if handler:
                handlers.append(handler)

        if cfg.get('ignoreSessCookies'):
            handlers.remove(self._cookieHandler)

        self._uri_opener = urllib2.build_opener(*handlers)

        # Prevent the urllib from putting his user-agent header
        self._uri_opener.addheaders = [('Accept', '*/*')]

    def get_custom_opener(self):
        return self._uri_opener

    def set_mangle_plugins(self, mp):
        '''
        Configure the mangle plugins to be used.

        @param mp: A list of mangle plugin instances.
        '''
        self._manglePlugins = mp

    def get_mangle_plugins(self):
        return self._manglePlugins

    def get_max_file_size(self):
        return cfg.get('maxFileSize')

    def set_maxFileSize(self, fsize):
        cfg.save('maxFileSize', fsize)

    def set_maxRetrys(self, retryN):
        cfg.save('maxRetrys', retryN)

    def get_max_retrys(self):
        return cfg.get('maxRetrys')

    def set_url_parameter(self, urlParam):
        # Do some input cleanup/validation
        urlParam = urlParam.replace("'", "")
        urlParam = urlParam.replace("\"", "")
        urlParam = urlParam.lstrip().rstrip()
        if urlParam != '':
            cfg.save('urlParameter', urlParam)
            self._urlParameterHandler = URLParameterHandler(urlParam)

    def get_url_parameter(self):
        return cfg.get('urlParameter')

    def get_options(self):
        '''
        @return: A list of option objects for this plugin.
        '''
        d1 = 'The timeout for connections to the HTTP server'
        h1 = 'Set low timeouts for LAN use and high timeouts for slow Internet connections.'
        o1 = opt_factory('timeout', cfg.get('timeout'), d1, 'integer', help=h1)

        d2 = 'Set the headers filename. This file has additional headers that are added to each request.'
        o2 = opt_factory('headersFile', cfg.get('headersFile'), d2, 'string')

        d3 = 'Set the basic authentication username for HTTP requests'
        o3 = opt_factory('basicAuthUser', cfg.get(
            'basicAuthUser'), d3, 'string', tabid='Basic HTTP Authentication')

        d4 = 'Set the basic authentication password for HTTP requests'
        o4 = opt_factory('basicAuthPass', cfg.get(
            'basicAuthPass'), d4, 'string', tabid='Basic HTTP Authentication')

        d5 = 'Set the basic authentication domain for HTTP requests'
        h5 = 'This configures on which requests to send the authentication settings configured'
        h5 += ' in basicAuthPass and basicAuthUser. If you are unsure, just set it to the'
        h5 += ' target domain name.'
        o5 = opt_factory('basicAuthDomain', cfg.get('basicAuthDomain'), d5,
                         'string', help=h5, tabid='Basic HTTP Authentication')

        d6a = 'Set the NTLM authentication domain (the windows domain name) for HTTP requests'
        o6a = opt_factory('ntlmAuthDomain', cfg.get(
            'ntlmAuthDomain'), d6a, 'string', tabid='NTLM Authentication')

        d6 = 'Set the NTLM authentication username for HTTP requests'
        o6 = opt_factory('ntlmAuthUser', cfg.get(
            'ntlmAuthUser'), d6, 'string', tabid='NTLM Authentication')

        d7 = 'Set the NTLM authentication password for HTTP requests'
        o7 = opt_factory('ntlmAuthPass', cfg.get(
            'ntlmAuthPass'), d7, 'string', tabid='NTLM Authentication')

        d7b = 'Set the NTLM authentication domain for HTTP requests'
        h7b = 'This configures on which requests to send the authentication settings configured'
        h7b += ' in ntlmAuthPass and ntlmAuthUser. If you are unsure, just set it to the'
        h7b += ' target domain name.'
        o7b = opt_factory('ntlmAuthURL', cfg.get(
            'ntlmAuthURL'), d7b, 'string', tabid='NTLM Authentication')

        d8 = 'Set the cookiejar filename.'
        h8 = 'The cookiejar file MUST be in mozilla format.'
        h8 += ' An example of a valid mozilla cookie jar file follows:\n\n'
        h8 += '# Netscape HTTP Cookie File\n'
        h8 += '.domain.com    TRUE   /       FALSE   1731510001      user    admin\n\n'
        h8 += 'The comment IS mandatory. Take special attention to spaces.'
        o8 = opt_factory('cookieJarFile', cfg.get(
            'cookieJarFile'), d8, 'string', help=h8, tabid='Cookies')

        d9 = 'Ignore session cookies'
        h9 = 'If set to True, w3af will ignore all session cookies sent by the web application.'
        o9 = opt_factory('ignoreSessCookies', cfg.get(
            'ignoreSessCookies'), d9, 'boolean', help=h9, tabid='Cookies')

        d10 = 'Proxy TCP port'
        h10 = 'TCP port for the remote proxy server to use. On Microsoft Windows systems, w3af'
        h10 += ' will use the proxy settings that are configured in Internet Explorer.'
        o10 = opt_factory('proxyPort', cfg.get(
            'proxyPort'), d10, 'integer', help=h10, tabid='Outgoing proxy')

        d11 = 'Proxy IP address'
        h11 = 'IP address for the remote proxy server to use. On Microsoft Windows systems, w3af'
        h11 += ' will use the proxy settings that are configured in Internet Explorer.'
        o11 = opt_factory('proxyAddress', cfg.get(
            'proxyAddress'), d11, 'string', help=h11, tabid='Outgoing proxy')

        d12 = 'User Agent header'
        h12 = 'User Agent header to send in request.'
        o12 = opt_factory('userAgent', cfg.get(
            'User-Agent'), d12, 'string', help=h12, tabid='Misc')

        d13 = 'Maximum file size'
        h13 = 'Indicates the maximum file size (in bytes) that w3af will GET/POST.'
        o13 = opt_factory('maxFileSize', cfg.get(
            'maxFileSize'), d13, 'integer', help=h13, tabid='Misc')

        d14 = 'Maximum number of retries'
        h14 = 'Indicates the maximum number of retries when requesting an URL.'
        o14 = opt_factory('maxRetrys', cfg.get(
            'maxRetrys'), d14, 'integer', help=h14, tabid='Misc')

        d15 = 'A comma separated list that determines what URLs will ALWAYS be detected as 404 pages.'
        o15 = opt_factory('always404', cfg.get(
            'always404'), d15, 'list', tabid='404 settings')

        d16 = 'A comma separated list that determines what URLs will NEVER be detected as 404 pages.'
        o16 = opt_factory('never404', cfg.get(
            'never404'), d16, 'list', tabid='404 settings')

        d17 = 'If this string is found in an HTTP response, then it will be tagged as a 404.'
        o17 = opt_factory('404string', cfg.get(
            '404string'), d17, 'string', tabid='404 settings')

        d18 = 'Append the given URL parameter to every accessed URL.'
        d18 += ' Example: http://www.foobar.com/index.jsp;<parameter>?id=2'
        o18 = opt_factory(
            'urlParameter', cfg.get('urlParameter'), d18, 'string')

        ol = OptionList()
        ol.add(o1)
        ol.add(o2)
        ol.add(o3)
        ol.add(o4)
        ol.add(o5)
        ol.add(o6a)
        ol.add(o6)
        ol.add(o7)
        ol.add(o7b)
        ol.add(o8)
        ol.add(o9)
        ol.add(o10)
        ol.add(o11)
        ol.add(o12)
        ol.add(o13)
        ol.add(o14)
        ol.add(o15)
        ol.add(o16)
        ol.add(o17)
        ol.add(o18)
        return ol

    def set_options(self, options_list):
        '''
        This method sets all the options that are configured using the user interface
        generated by the framework using the result of get_options().

        @param options_list: An OptionList with the option objects for a plugin.
        @return: No value is returned.
        '''
        getOptsMapValue = lambda n: options_list[n].get_value()
        self.set_timeout(getOptsMapValue('timeout'))

        # Only apply changes if they exist
        bAuthDomain = getOptsMapValue('basicAuthDomain')
        bAuthUser = getOptsMapValue('basicAuthUser')
        bAuthPass = getOptsMapValue('basicAuthPass')

        if bAuthDomain != cfg['basicAuthDomain'] or \
            bAuthUser != cfg['basicAuthUser'] or \
                bAuthPass != cfg['basicAuthPass']:
            try:
                bAuthDomain = URL(bAuthDomain) if bAuthDomain else ''
            except ValueError:
                bAuthDomain = None

            self.set_basic_auth(bAuthDomain, bAuthUser, bAuthPass)

        ntlmAuthDomain = getOptsMapValue('ntlmAuthDomain')
        ntlmAuthUser = getOptsMapValue('ntlmAuthUser')
        ntlmAuthPass = getOptsMapValue('ntlmAuthPass')
        ntlmAuthURL = getOptsMapValue('ntlmAuthURL')

        if ntlmAuthDomain != cfg['ntlmAuthDomain'] or \
            ntlmAuthUser != cfg['ntlmAuthUser'] or \
            ntlmAuthPass != cfg['ntlmAuthPass'] or \
                ntlmAuthURL != cfg['ntlmAuthURL']:
            self.set_ntlm_auth(
                ntlmAuthURL, ntlmAuthDomain, ntlmAuthUser, ntlmAuthPass)

        # Only apply changes if they exist
        proxyAddress = getOptsMapValue('proxyAddress')
        proxyPort = getOptsMapValue('proxyPort')

        if proxyAddress != cfg['proxyAddress'] or \
                proxyPort != cfg['proxyPort']:
            self.set_proxy(proxyAddress, proxyPort)

        self.set_cookieJarFile(getOptsMapValue('cookieJarFile'))
        self.set_headersFile(getOptsMapValue('headersFile'))
        self.set_user_agent(getOptsMapValue('userAgent'))
        cfg['ignoreSessCookies'] = getOptsMapValue('ignoreSessCookies')

        self.set_maxFileSize(getOptsMapValue('maxFileSize'))
        self.set_maxRetrys(getOptsMapValue('maxRetrys'))

        self.set_url_parameter(getOptsMapValue('urlParameter'))

        # 404 settings are saved here
        cfg['never404'] = getOptsMapValue('never404')
        cfg['always404'] = getOptsMapValue('always404')
        cfg['404string'] = getOptsMapValue('404string')

    def get_desc(self):
        return ('This section is used to configure URL settings that '
                'affect the core and all plugins.')
