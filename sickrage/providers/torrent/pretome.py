# Author: Nick Sologoub
# URL: http://github.com/SiCKRAGETV/SickRage/
#
# This file is part of SickRage.
#
# SickRage is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# SickRage is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with SickRage.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import unicode_literals

import re
import traceback
import urllib

import sickrage
from sickrage.core.caches import tv_cache
from sickrage.core.helpers import bs4_parser
from sickrage.providers import TorrentProvider


class PretomeProvider(TorrentProvider):
    def __init__(self):
        super(PretomeProvider, self).__init__("Pretome")

        self.supportsBacklog = True

        self.username = None
        self.password = None
        self.pin = None
        self.ratio = None
        self.minseed = None
        self.minleech = None

        self.urls = {'base_url': 'https://pretome.info',
                     'login': 'https://pretome.info/takelogin.php',
                     'detail': 'https://pretome.info/details.php?id=%s',
                     'search': 'https://pretome.info/browse.php?search=%s%s',
                     'download': 'https://pretome.info/download.php/%s/%s.torrent'}

        self.url = self.urls['base_url']

        self.categories = "&st=1&cat%5B%5D=7"

        self.proper_strings = ['PROPER', 'REPACK']

        self.cache = PretomeCache(self)

    def _checkAuth(self):

        if not self.username or not self.password or not self.pin:
            sickrage.LOGGER.warning("Invalid username or password or pin. Check your settings")

        return True

    def _doLogin(self):

        login_params = {'username': self.username,
                        'password': self.password,
                        'login_pin': self.pin}

        response = self.getURL(self.urls['login'], post_data=login_params, timeout=30)
        if not response:
            sickrage.LOGGER.warning("Unable to connect to provider")
            return False

        if re.search('Username or password incorrect', response):
            sickrage.LOGGER.warning("Invalid username or password. Check your settings")
            return False

        return True

    def _doSearch(self, search_params, search_mode='eponly', epcount=0, age=0, epObj=None):

        results = []
        items = {'Season': [], 'Episode': [], 'RSS': []}

        if not self._doLogin():
            return results

        for mode in search_params.keys():
            sickrage.LOGGER.debug("Search Mode: %s" % mode)
            for search_string in search_params[mode]:

                if mode is not 'RSS':
                    sickrage.LOGGER.debug("Search string: %s " % search_string)

                searchURL = self.urls['search'] % (urllib.quote(search_string.encode('utf-8')), self.categories)
                sickrage.LOGGER.debug("Search URL: %s" % searchURL)

                data = self.getURL(searchURL)
                if not data:
                    continue

                try:
                    with bs4_parser(data) as html:
                        # Continue only if one Release is found
                        empty = html.find('h2', text="No .torrents fit this filter criteria")
                        if empty:
                            sickrage.LOGGER.debug("Data returned from provider does not contain any torrents")
                            continue

                        torrent_table = html.find('table', attrs={'style': 'border: none; width: 100%;'})
                        if not torrent_table:
                            sickrage.LOGGER.error("Could not find table of torrents")
                            continue

                        torrent_rows = torrent_table.find_all('tr', attrs={'class': 'browse'})

                        for result in torrent_rows:
                            cells = result.find_all('td')
                            size = None
                            link = cells[1].find('a', attrs={'style': 'font-size: 1.25em; font-weight: bold;'})

                            torrent_id = link[b'href'].replace('details.php?id=', '')

                            try:
                                if link.has_key('title'):
                                    title = link[b'title']
                                else:
                                    title = link.contents[0]

                                download_url = self.urls['download'] % (torrent_id, link.contents[0])
                                seeders = int(cells[9].contents[0])
                                leechers = int(cells[10].contents[0])

                                # Need size for failed downloads handling
                                if size is None:
                                    if re.match(r'[0-9]+,?\.?[0-9]*[KkMmGg]+[Bb]+', cells[7].text):
                                        size = self._convertSize(cells[7].text)
                                        if not size:
                                            size = -1

                            except (AttributeError, TypeError):
                                continue

                            if not all([title, download_url]):
                                continue

                            # Filter unseeded torrent
                            if seeders < self.minseed or leechers < self.minleech:
                                if mode is not 'RSS':
                                    sickrage.LOGGER.debug(
                                            "Discarding torrent because it doesn't meet the minimum seeders or leechers: {0} (S:{1} L:{2})".format(
                                                    title, seeders, leechers))
                                continue

                            item = title, download_url, size, seeders, leechers
                            if mode is not 'RSS':
                                sickrage.LOGGER.debug("Found result: %s " % title)

                            items[mode].append(item)

                except Exception as e:
                    sickrage.LOGGER.error("Failed parsing provider. Traceback: %s" % traceback.format_exc())

            # For each search mode sort all the items by seeders if available
            items[mode].sort(key=lambda tup: tup[3], reverse=True)

            results += items[mode]

        return results

    def seedRatio(self):
        return self.ratio

    @staticmethod
    def _convertSize(sizeString):
        size = sizeString[:-2]
        modifier = sizeString[-2:]
        size = float(size)
        if modifier in 'KB':
            size = size * 1024
        elif modifier in 'MB':
            size = size * 1024 ** 2
        elif modifier in 'GB':
            size = size * 1024 ** 3
        elif modifier in 'TB':
            size = size * 1024 ** 4
        return int(size)


class PretomeCache(tv_cache.TVCache):
    def __init__(self, provider_obj):
        tv_cache.TVCache.__init__(self, provider_obj)

        # only poll Pretome every 20 minutes max
        self.minTime = 20

    def _getRSSData(self):
        search_params = {'RSS': ['']}
        return {'entries': self.provider._doSearch(search_params)}
