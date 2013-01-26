# -*- coding: utf-8 -*-

from anki.hooks import addHook
from aqt import mw
from aqt.utils import showInfo


def editor_download_and_insert_noun_info(self):
    self.saveNow()

    word = strip_accents(self.note['headword.singular'])
    new_fields = flatten(extract_noun_info(download_noun_html(word)))

    for field, val in new_fields.items():
        if field in self.note:
            self.note[field] = val

    self.loadNote()


def editor_add_download_noun_icon(self):
    self._addButton("dictionare_download_noun",
                    lambda self=self: editor_download_and_insert_noun_info(self),
        tip=u"Download noun declensions from Dictionare", text=u"DN")


def editor_add_download_verb_icon(self):
    pass


addHook("setupEditorButtons", editor_add_download_noun_icon)
addHook("setupEditorButtons", editor_add_download_verb_icon)


###########################


import re
import unicodedata
import urllib

from BSXPath import BSXPathEvaluator, XPathResult


DICTIONARE_NOUN_PAGE_URL = "http://www.dictionare.com/phpdic/nouns.php?field0=%s"


def strip_accents(word):
    return ''.join((c for c in unicodedata.normalize('NFD', word) if unicodedata.category(c) != 'Mn'))


# Flatten a dictionary to one level, merging its keys so that they are
# separated by dots.
def flatten(d, delimiter='.', parent_key=''):
    new = []

    for k, v in d.items():
        k = parent_key + delimiter + k if parent_key else k

        if isinstance(v, dict):
            new.extend(flatten(v, parent_key=k).items())
        else:
            new.append((k, v))

    return dict(new)


def download_noun_html(word):
    """
    Download a noun declension information from Dictionare. Returns HTML
    content parsed by BeautifulSoup.
    """

    url = DICTIONARE_NOUN_PAGE_URL % word
    handle = urllib.urlopen(url)
    html = handle.read()
    handle.close()

    # Encoding
    html = html.decode('iso8859_2').encode('utf-8')

    # Aiming for minimum pain here.
    # The comment syntax on this page is wrong.. :(
    important_html = re.search('<!-- Start text --!>(.+)<!-- End text --!>',
                               html, re.S).group(1)

    # Parse as a fragment
    parsed = BSXPathEvaluator('<html><body>%s</body></html>' % important_html)

    return parsed


def extract_noun_info(html):
    """
    Build structured information about noun declensions from a
    Dictionare noun page.
    """

    noun_data = {
        'headword': {
            'singular': None,
            'plural': None,
            'gender': None
        },

        'declensions': {
            'indefinite': {
                'singular': {'nominative': None, 'genitive': None, 'dative': None, 'accusative': None},
                'plural': {'nominative': None, 'genitive': None, 'dative': None, 'accusative': None}
            },
            'definite': {
                'singular': {'nominative': None, 'genitive': None, 'dative': None, 'accusative': None},
                'plural': {'nominative': None, 'genitive': None, 'dative': None, 'accusative': None}
            }
        }
    }

    main_noun_container = html.getFirstItem('html/body/center[3]/center[1]/table[1]/tbody[1]/tr[1]/td[1]/center[1]/table[1]/tbody[1]')

    headword_container = html.getFirstItem('tr[1]/td[1]', main_noun_container)
    noun_data['headword']['singular'] = html.getFirstItem('b[1]/font/font', headword_container).findAll(text=True)[1]
    noun_data['headword']['plural'] = re.sub('^/ ', '', html.getFirstItem('b[2]', headword_container).text)
    noun_data['headword']['gender'] = headword_container.findAll(text=True)[-1].strip()

    declension_container = html.getFirstItem('tr[3]', main_noun_container)
    indefinite_declensions = html.getFirstItem('td[1]/table/tbody/tr[1]', declension_container)
    definite_declensions = html.getFirstItem('td[2]/table/tbody/tr[1]', declension_container)

    # Cases are listed in the same order for all four article /
    # plurality combinations. Let's save some typing.
    case_index_pairs = {
        'nominative': 0,
        'genitive': 1,
        'dative': 2,
        'accusative': 3
    }

    # Grab all text nodes and pick out the indices we know to be correct
    indefinite_singular_declensions = html.getFirstItem('td[1]', indefinite_declensions).findAll(text=True)
    for case, idx in case_index_pairs.items():
        noun_data['declensions']['indefinite']['singular'][case] = indefinite_singular_declensions[3 + 2 * idx]

    indefinite_plural_declensions = html.getFirstItem('td[2]', indefinite_declensions).findAll(text=True)
    for case, idx in case_index_pairs.items():
        noun_data['declensions']['indefinite']['plural'][case] = indefinite_plural_declensions[2 + 2 * idx]

    definite_singular_declensions = html.getFirstItem('td[2]', definite_declensions).findAll(text=True)
    for case, idx in case_index_pairs.items():
        noun_data['declensions']['definite']['singular'][case] = definite_singular_declensions[3 + 2 * idx]

    definite_plural_declensions = html.getFirstItem('td[3]', definite_declensions).findAll(text=True)
    for case, idx in case_index_pairs.items():
        noun_data['declensions']['definite']['plural'][case] = definite_plural_declensions[3 + 2 * idx]

    return noun_data
