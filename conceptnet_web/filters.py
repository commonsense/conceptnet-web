from jinja2.ext import Markup
from conceptnet5.languages import get_language_name
from conceptnet5.uri import split_uri, uri_prefix
from .json_rendering import highlight_and_link_json


def describe_term_language(lang, description_language='en'):
    if description_language != 'en':
        raise NotImplementedError(
            "We don't support non-English interface text yet."
        )

    language_name = get_language_name(lang, description_language)
    if language_name[0] in 'AEIOU' and not language_name.startswith('Uk'):
        article = 'An'
    else:
        article = 'A'

    content = '{article} <a href="/c/{lang}">{language_name}</a> term'.format(
        article=article, lang=lang, language_name=language_name
    )
    return Markup(content)


def source_link(url, name):
    linked = '<a href="{url}">{name}</a>'.format(
        url=url, name=name
    )
    return linked


CONTRIBUTOR_NAME_MAP = {
    '/s/resource/verbosity': 'Verbosity players',
    '/s/resource/wordnet/rdf/3.1': 'Open Multilingual WordNet',
    '/s/resource/opencyc/2012': 'OpenCyc 2012',
    '/s/resource/jmdict/1.07': 'JMDict 1.07',
    '/s/resource/dbpedia/2015/en': 'DBPedia 2015',

}


ERROR_NAME_MAP = {
    400: 'Bad request',
    404: 'Not found',
    429: 'Too many requests',
    500: 'Server error'
}


def error_name(code):
    return ERROR_NAME_MAP.get(code, 'Unknown error %r' % code)


def oxford_comma(items):
    if len(items) == 0:
        return ''
    elif len(items) == 1:
        return items[0]
    elif len(items) == 2:
        return "{0} and {1}".format(*items)
    else:
        comma_sep = ', '.join(items[:-1])
        last = items[-1]
        return "{0}, and {1}".format(comma_sep, last)


MAX_INDIVIDUALS = 3


def describe_sources(sources, specific=True):
    omcs_contributors = []
    omcs_count = 0
    ptt_count = 0
    nadya_count = 0
    more_sources = set()

    for source in sources:
        if 'activity' in source and source['activity'] == '/s/activity/omcs/nadya.jp':
            nadya_count += 1
        elif 'contributor' in source:
            contributor = source['contributor']
            prefix = uri_prefix(contributor, 3)
            if prefix == '/s/contributor/omcs':
                if len(omcs_contributors) < MAX_INDIVIDUALS:
                    name = split_uri(contributor)[-1]
                    omcs_contributors.append(source_link(contributor, name))
                omcs_count += 1
            elif prefix == '/s/contributor/petgame':
                ptt_count += 1
            elif prefix == '/s/resource/en.wiktionary.org':
                more_sources.add(source_link(prefix, "English Wiktionary"))
            elif prefix == '/s/resource/de.wiktionary.org':
                more_sources.add(source_link(prefix, "German Wiktionary"))
            elif prefix == '/s/resource/fr.wiktionary.org':
                more_sources.add(source_link(prefix, "French Wiktionary"))
            elif contributor in CONTRIBUTOR_NAME_MAP:
                more_sources.add(source_link(contributor, CONTRIBUTOR_NAME_MAP[contributor]))
            else:
                more_sources.add(source_link(contributor, contributor))

    source_chunks = []
    if omcs_contributors:
        if specific:
            if omcs_count > MAX_INDIVIDUALS:
                omcs_contributors.append("{} more".format(omcs_count - MAX_INDIVIDUALS))

            omcs_str = '<a href="/s/activity/omcs">Open Mind Common Sense</a> contributors {}'.format(
                oxford_comma(omcs_contributors)
            )
            source_chunks.append(omcs_str)
        else:
            source_chunks.append('<a href="/s/activity/omcs">Open Mind Common Sense</a> contributors')
    if ptt_count:
        if specific:
            if ptt_count == 1:
                count_str = "a player"
            else:
                count_str = "{} players".format(ptt_count)
            source_chunks.append(
                '{} of the <a href="/s/contributor/petgame">PTT Pet Game</a>'.format(count_str)
            )
        else:
            source_chunks.append('the <a href="/s/contributor/petgame">PTT Pet Game</a>')

    if nadya_count:
        if specific:
            if nadya_count == 1:
                count_str = "a player"
            else:
                count_str = "{} players".format(nadya_count)
            source_chunks.append(
                '{} of <a href="/s/activity/omcs/nadya.jp">nadya.jp</a>'.format(count_str)
            )
        else:
            source_chunks.append('<a href="/s/activity/omcs/nadya.jp">nadya.jp</a>')

    source_chunks.extend(sorted(more_sources))
    if len(source_chunks) == 1:
        source_markup = "<strong>Source:</strong> {}".format(source_chunks[0])
    else:
        source_markup = "<strong>Sources:</strong> {}".format(oxford_comma(source_chunks))
    return Markup(source_markup)


def describe_sources_brief(sources):
    return describe_sources(sources, False)


FILTERS = {
    'highlight_json': highlight_and_link_json,
    'describe_term_language': describe_term_language,
    'describe_sources': describe_sources,
    'describe_sources_brief': describe_sources_brief,
    'error_name': error_name
}
