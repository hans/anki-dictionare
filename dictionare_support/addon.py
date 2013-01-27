# -*- coding: utf-8 -*-

from anki.hooks import addHook
from aqt import mw
from aqt.utils import askUserDialog, showInfo
from PyQt4.QtGui import QPushButton


def download_and_insert_info(self, note_search_key, download_function,
                           preliminary_extraction_function,
                           final_extraction_function):
    self.saveNow()

    word = self.note[note_search_key]
    word_stripped = strip_accents(word)

    html = download_function(word_stripped)
    main_containers = preliminary_extraction_function(html)

    infos = [flatten(final_extraction_function(html, cont))
             for cont in main_containers]

    result = None
    if len(infos) > 1:
        # We got more than one result in the server response. Try to
        # resolve on our own by comparing the result (including
        # diacritics) with what the user input; if there's no definite
        # match, then ask the user.
        for info in infos:
            if compare_romanian_words(info[note_search_key], word):
                result = info
                break

            if result is None:
                keyed_results = {i[note_search_key]: i for i in infos}
                decision = ask_user_word(keyed_results.keys())

                if decision is None:
                    return
                else:
                    result = keyed_results[decision]
    else:
        result = infos[0]

    for field, val in result.items():
        if field in self.note:
            self.note[field] = val

    self.loadNote()


def editor_download_and_insert_noun_info(self):
    download_and_insert_info(self, 'headword.singular', download_noun_html,
                             do_preliminary_noun_extraction, extract_noun_info)


def editor_download_and_insert_verb_info(self):
    download_and_insert_info(self, 'headword', download_verb_html,
                             do_preliminary_verb_extraction, extract_verb_info)


def editor_add_download_noun_icon(self):
    self._addButton("dictionare_download_noun",
                    lambda self=self: editor_download_and_insert_noun_info(self),
        tip=u"Download noun declensions from Dictionare", text=u"DN")


def editor_add_download_verb_icon(self):
    self._addButton("dictionare_download_noun",
                    lambda self=self: editor_download_and_insert_verb_info(self),
        tip=u"Download verb conjugations from Dictionare", text=u"DV")


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


import operator
import re
import unicodedata
import urllib

from BSXPath import BSXPathEvaluator, XPathResult


DICTIONARE_NOUN_PAGE_URL = "http://www.dictionare.com/phpdic/nouns.php?field0=%s"
DICTIONARE_VERB_PAGE_URL = "http://www.dictionare.com/phpdic/verbs.php?field0=%s"


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


def download_html(word, url_template):
    """
    Download a noun declension information from Dictionare. Returns HTML
    content parsed by BeautifulSoup.
    """

    url = url_template % word
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


def download_noun_html(noun):
    return download_html(noun, DICTIONARE_NOUN_PAGE_URL)


def download_verb_html(verb):
    return download_html(verb, DICTIONARE_VERB_PAGE_URL)


def do_preliminary_noun_extraction(html):
    """
    Pull out a list of nouns displayed on the given page. This
    function's return (element-by-element) should be passed to
    `extract_noun_info`.
    """

    main_noun_containers = html.getItemList('html/body/center[3]/center[1]/'
                                            'table[1]/tbody[1]/tr[1]/td[1]'
                                            '/center/table[1]/tbody[1]')
    return main_noun_containers


def do_preliminary_verb_extraction(html):
    """
    Pull out a verb displayed on a given page. This function's return
    should be passed to `extract_verb_info`.
    """

    return [html.getFirstItem('html/body/center[3]/center[1]/table[1]/tbody[1]'
                              '/tr[1]/td[1]/center[1]/table[1]/tbody[1]')]


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
    plural_text = html.getFirstItem('b[2]', headword_container).text
    gender_text = headword_container.findAll(text=True)[-1]

    noun_data['headword']['singular'] = ( html.getFirstItem('b[1]/font/font',
                                                            headword_container)
                                          .findAll(text=True)[1] )
    noun_data['headword']['plural'] = re.sub('^/ ', '', plural_text)
    noun_data['headword']['gender'] = gender_text.strip()

    declension_container = html.getFirstItem('tr[3]', main_noun_container)
    indefinite_declensions = html.getFirstItem('td[1]/table/tbody/tr[1]',
                                               declension_container)
    definite_declensions = html.getFirstItem('td[2]/table/tbody/tr[1]',
                                             declension_container)

    # Cases are listed in the same order for all four article /
    # plurality combinations. Let's save some typing.
    case_index_pairs = {
        'nominative': 0,
        'genitive': 1,
        'dative': 2,
        'accusative': 3
    }

    # Grab all text nodes and pick out the indices we know to be correct
    indefinite_singular_declensions = ( html.getFirstItem('td[1]',
                                                          indefinite_declensions)
                                        .findAll(text=True) )

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

def extract_verb_info(html, main_verb_container):
    """
    Build a dict describing all of a verb's conjugations given rendered content.
    """

    verb_data = {
        'headword': None,
        'gerund': None,
        'past_participle': None,
        'conj': {
            'ind': {
                'prs': {'1sg': None, '2sg': None, '3sg': None, '1pl': None, '2pl': None, '3pl': None},
                'perfcomp': {'1sg': None, '2sg': None, '3sg': None, '1pl': None, '2pl': None, '3pl': None},
                'imperf': {'1sg': None, '2sg': None, '3sg': None, '1pl': None, '2pl': None, '3pl': None},
                'pastperf': {'1sg': None, '2sg': None, '3sg': None, '1pl': None, '2pl': None, '3pl': None},
                'future1': {'1sg': None, '2sg': None, '3sg': None, '1pl': None, '2pl': None, '3pl': None},
                'future2': {'1sg': None, '2sg': None, '3sg': None, '1pl': None, '2pl': None, '3pl': None},
                'future1pop': {'1sg': None, '2sg': None, '3sg': None, '1pl': None, '2pl': None, '3pl': None},
                'future2pop': {'1sg': None, '2sg': None, '3sg': None, '1pl': None, '2pl': None, '3pl': None},
                'future3pop': {'1sg': None, '2sg': None, '3sg': None, '1pl': None, '2pl': None, '3pl': None},
                'simpperf': {'1sg': None, '2sg': None, '3sg': None, '1pl': None, '2pl': None, '3pl': None}
            },
            'subj': {
                'prs': {'1sg': None, '2sg': None, '3sg': None, '1pl': None, '2pl': None, '3pl': None},
                'perfcomp': {'1sg': None, '2sg': None, '3sg': None, '1pl': None, '2pl': None, '3pl': None},
            },
            'cond': {
                'prs': {'1sg': None, '2sg': None, '3sg': None, '1pl': None, '2pl': None, '3pl': None},
                'perf': {'1sg': None, '2sg': None, '3sg': None, '1pl': None, '2pl': None, '3pl': None},
            },
            'imp': {'2sg': None, '2pl': None}
        }
    }

    headword_contents = html.getFirstItem('tr[1]', main_verb_container).findAll(text=True)
    verb_data['headword'] = headword_contents[1]
    verb_data['gerund'] = headword_contents[3].strip()
    verb_data['past_participle'] = headword_contents[5]

    # Describes the order in which conjugations appear in the page source
    conj_order = ['ind.prs', 'ind.perfcomp', 'ind.imperf', 'ind.pastperf',
                  'ind.simpperf', 'subj.prs', 'subj.perfcomp', 'imp',
                  'ind.future1', 'ind.future2', 'ind.future1pop',
                  'ind.future2pop', 'ind.future3pop', 'cond.prs', 'cond.perf']

    # In some conjugations the verb is given first and in others the
    # pronoun first. If we have a tuple for a given conjugation `(el0,
    # el1)`, which is the verb?
    verb_index = {
        'ind.prs': 1,
        'ind.perfcomp': 1,
        'ind.imperf': 1,
        'ind.pastperf': 1,
        'ind.simpperf': 1,
        'subj.prs': 0,
        'subj.perfcomp': 0,
        'imp': 0,
        'ind.future1': 1,
        'ind.future2': 1,
        'ind.future1pop': 0,
        'ind.future2pop': 0,
        'ind.future3pop': 0,
        'cond.prs': 1,
        'cond.perf': 1
    }

    conjugation_pair_els = html.getItemList('tr[3]/td//table/tbody[1]/tr/td[count(font)>1]/font/font', main_verb_container)
    conjugation_pronoun_pairs = [x.findAll(text=True) for x in conjugation_pair_els]
    print conjugation_pronoun_pairs

    # We'll move a window through the conjugation pair "stack." This
    # cursor tracks the start of the window.
    cursor = 0

    for conj in conj_order:
        # How many conjugations should we take off the stack?
        take = 2 if conj == 'imp' else 6
        pairs = conjugation_pronoun_pairs[cursor:cursor+take]
        cursor += take

        # Pick out the verbs from the pairs for this conjugation
        verbs = [p[verb_index[conj]].strip() for p in pairs]

        configurations = (['2sg', '2pl'] if conj == 'imp'
                          else ['1sg', '2sg', '3sg', '1pl', '2pl', '3pl'])
        conjugations = dict(zip(configurations, verbs))

        if conj == 'imp':
            verb_data['conj']['imp'] = conjugations
        else:
            p1, p2 = conj.split('.')
            verb_data['conj'][p1][p2] = conjugations

    return verb_data
