# -*- coding: utf-8 -*-

from anki.hooks import addHook
from aqt import mw
from aqt.utils import askUserDialog, showInfo
from PyQt4.QtGui import QPushButton


def editor_download_and_insert_noun_info(self):
    self.saveNow()

    word = self.note['headword.singular']
    word_stripped = strip_accents(word)

    html = download_noun_html(word_stripped)
    main_noun_containers = do_preliminary_extraction(html)

    noun_infos = [flatten(extract_noun_info(html, cont))
                  for cont in main_noun_containers]

    noun_result = None
    if len(noun_infos) > 1:
        # We got more than one result in the server response. Try to
        # resolve on our own by comparing the result (including
        # diacritics) with what the user input; if there's no definite
        # match, then ask the user.
        for noun_info in noun_infos:
            if compare_romanian_words(noun_info['headword.singular'], word):
                noun_result = noun_info
                break

        if noun_result is None:
            keyed_results = {n['headword.singular']: n for n in noun_infos}
            decision = ask_user_word(keyed_results.keys())

            if decision is None:
                return
            else:
                noun_result = keyed_results[decision]
    else:
        noun_result = noun_infos[0]

    for field, val in noun_result.items():
        if field in self.note:
            self.note[field] = val

    self.loadNote()


def editor_add_download_noun_icon(self):
    self._addButton("dictionare_download_noun",
                    lambda self=self: editor_download_and_insert_noun_info(self),
        tip=u"Download noun declensions from Dictionare", text=u"DN")


def editor_add_download_verb_icon(self):
    pass


def ask_user_word(words):
    """
    Ask the user to choose between multiple word results.

    Returns the word selected or `None` if the user cancels the action.
    """

    buttons = map(QPushButton, words + ['Cancel'])
    dialog = askUserDialog('Multiple results were found. Which should be used?',
                           buttons)
    result = dialog.run()

    if result == 'Cancel':
        return None
    return result


def compare_romanian_words(s1, s2):
    """
    Some Romanian texts use cedillas and other use commas. Regularize
    first and then compare.
    """

    replacements = {u'Ş': u'Ș', u'ş': u'ș', u'Ţ': u'Ț', u'ţ': u'ț'}

    for search, replace in replacements.items():
        s1 = s1.replace(search, replace)
        s2 = s2.replace(search, replace)

    return s1 == s2


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


def do_preliminary_extraction(html):
    """
    Pull out a list of nouns displayed on the given page. This
    function's return (element-by-element) should be passed to
    `extract_noun_info`.
    """

    main_noun_containers = html.getItemList('html/body/center[3]/center[1]/table[1]/tbody[1]/tr[1]/td[1]/center/table[1]/tbody[1]')
    return main_noun_containers


def extract_noun_info(html, main_noun_container):
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
