from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

from future.moves.urllib.parse import urlencode
from bs4 import BeautifulSoup, element
import logging

from flexget import plugin
from flexget.event import event
from flexget.plugin import PluginError

log = logging.getLogger('torznab')


class Torznab(object):
    """Torznab search plugin

    Handles searching for tv shows and movies, with fallback to simple query strings if these are not available.
    """

    @property
    def schema(self):
        """The schema of the plugin"""
        schema = {
            'type': 'object',
            'properties': {
                'apikey': {'type': 'string'},
                'categories': {'type': 'array', 'items': {'type': 'integer'}, 'default': []},
                'searcher': {'type': 'string', 'enum': ['movie', 'tv', 'tvsearch', 'search'], 'default': 'search'},
                'website': {'type': 'string', 'format': 'url'}
            },
            'required': ['website', 'apikey'],
            'additionalProperties': False
        }
        return schema

    def search(self, task, entry, config=None):
        """Search interface"""
        self._setup(task, config)
        return []

    def _build_url(self, **kwargs):
        """Builds the url with query parameters from the arguments"""
        params = self.params.copy()
        params.update(kwargs)
        log.debug('Configured parameters: {}'.format(params))
        url = '{}/api?'.format(self.base_url)
        url = '{}{}'.format(url, urlencode(params))
        return url

    def _setup(self, task, config):
        """Set up parameters"""
        self.base_url = config['website'].rstrip('/')
        self.supported_params = []
        if config['searcher'] == 'tv':
            config['searcher'] = 'tvsearch'

        self.params = {
            'apikey': config['apikey'],
            'extended': 1,
        }

        log.debug('Config: {}'.format(config))
        self._setup_caps(task, config['searcher'], config['categories'])

    @plugin.internet(log)
    def _setup_caps(self, task, searcher, categories):
        """Gets the capabilities of the torznab indexer and matches it with the provided configuration"""

        response = task.requests.get(self._build_url(t='caps'))
        log.debug('Raw caps response {}'.format(response.content))
        root = BeautifulSoup(response.content, 'lxml')
        self._setup_searcher(root, searcher)
        self._setup_categories(root, categories)

    def _setup_searcher(self, xml_root, searcher):
        """Gets the available searchers (tv, movie, etc) for the indexer and their supported parameters"""
        aliases = {
            'movie': 'movie-search',
            'search': 'search',
            'tvsearch': 'tv-search'
        }

        searchers = {item.name: item.attrs for item in list(xml_root.find('searching')) if type(item) == element.Tag}
        if searchers:
            if self._check_searcher(searchers, aliases[searcher]):
                self.supported_params = searchers[aliases[searcher]]['supportedparams'].split(',')
                self.params['t'] = searcher
                log.debug("Searcher '{}' set up with '{}' parameters".format(
                         aliases[searcher],
                         self.supported_params))
            elif searcher != 'search' and self._check_searcher(searchers, 'search'):
                log.warn("'{}' searcher not availble, falling back to 'search'.".format(aliases[searcher]))
                self.supported_params = searchers['search']['supportedparams'].split(',')
                self.params['t'] = 'search'
                log.debug("Searcher '{}' set up with '{}' parameters".format(
                         aliases[searcher],
                         self.supported_params))
            else:
                raise PluginError('No searcher available on {}'.format(self.base_url))
        else:
            raise PluginError('No searcher available on {}'.format(self.base_url))

    def _check_searcher(self, searchers, searcher):
        """Check if the given searchers is in the list, available and has supported params"""
        return searcher in searchers.keys() and \
            searchers[searcher]['available'] == 'yes' and \
            searchers[searcher]['supportedparams']

    def _setup_categories(self, xml_root, categories):
        """Gets the available search categories for the indexer"""
        pass


@event('plugin.register')
def register_plugin():
    plugin.register(Torznab, 'torznab', api_ver=2, interfaces=['search'])
