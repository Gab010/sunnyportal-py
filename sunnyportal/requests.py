# Copyright (c) 2016 Erik Johansson <erik@ejohansson.se>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307
# USA

from . import responses

from datetime import datetime

import base64
import hashlib
import hmac
import http.client as http
import logging
import re
import urllib.parse


class RequestBase(object):
    def __init__(self, service, token=None, method='GET'):
        super().__init__()
        self.log = logging.getLogger(__name__)
        self.service = service
        self.token = token
        self.method = method
        self.version = 100
        self.base_path = '/services'
        self.url = None

    def get_timestamp(self, offset):
        timestamp = datetime.now() - offset
        return timestamp.strftime("%Y-%m-%dT%H:%M:%S")

    def prepare_url(self, path, params={}):
        if self.token is not None:
            sig = hmac.new(self.token.key.encode(), digestmod=hashlib.sha1)
            sig.update(self.method.lower().encode())
            sig.update(self.service.lower().encode())

            ts = self.get_timestamp(self.token.server_offset)
            sig.update(ts.encode())
            params['timestamp'] = ts

            sig.update(self.token.identifier.lower().encode())

            params['signature-method'] = 'auth'
            params['signature-version'] = self.version
            params['signature'] = base64.standard_b64encode(sig.digest())

        self.url = "%s/%s/%d/%s" % (
            self.base_path, self.service, self.version,
            urllib.parse.quote(path))
        if params:
            self.url += "?%s" % urllib.parse.urlencode(params)

    def log_request(self, method, url):
        self.log.debug("%s %s", method, url)

    def perform(self, connection):
        assert(self.url is not None)

        self.log_request(self.method, self.url)
        connection.request(self.method, self.url)

        response = connection.getresponse()
        if response.status != http.OK:
            raise RuntimeError(
                "HTTP error performing {} request: {} {}".format(
                    self.service, response.status, response.reason))

        data = response.read().decode("utf-8")
        return self.handle_response(data)


class AuthenticationRequest(RequestBase):
    def __init__(self, username, password):
        super().__init__(service='authentication')
        self.password = password
        self.prepare_url(username, {'password': password})

    def log_request(self, method, url):
        password = urllib.parse.quote_plus(self.password)
        super().log_request(method, url.replace(password, '<password>'))

    def handle_response(self, data):
        return responses.AuthenticationResponse(data)


class LogoutRequest(RequestBase):
    def __init__(self, token):
        super().__init__(service='authentication', token=token,
                         method='DELETE')
        self.prepare_url(token.identifier)

    def handle_response(self, data):
        return responses.AuthenticationResponse(data)


class PlantListRequest(RequestBase):
    def __init__(self, token):
        super().__init__(service='plantlist', token=token)
        self.prepare_url(token.identifier)

    def handle_response(self, data):
        return responses.PlantListResponse(data)