from conceptnet5.query import AssertionFinder, field_match, VALID_KEYS
from conceptnet5.relations import SYMMETRIC_RELATIONS
from conceptnet5.uri import uri_prefix
from conceptnet5.nodes import standardized_concept_uri
from collections import defaultdict
import itertools

FINDER = AssertionFinder()
VALID_KEYS = VALID_KEYS   # re-export
CONTEXT = [
    "http://api.conceptnet.io/ld/conceptnet5.5/context.ld.json",
    "http://api.conceptnet.io/ld/conceptnet5.5/pagination.ld.json"
]


def success(response):
    response['@context'] = CONTEXT
    return response


def error(response, status, details):
    response['@context'] = CONTEXT
    response['error'] = {
        'status': status,
        'details': details
    }
    return response


def make_query_url(url, items):
    str_items = ['{}={}'.format(*item) for item in items]
    if not str_items:
        return url
    else:
        return url + '?' + ('&'.join(str_items))


def groupkey_to_features(groupkey):
    groupdict = dict(groupkey)
    if 'node' in groupdict:
        return ['{} {} -'.format(groupdict['node'], groupdict['rel']),
                '- {} {}'.format(groupdict['rel'], groupdict['node'])]
    else:
        feat = '{} {} {}'.format(
            groupdict.get('start', '-'),
            groupdict.get('rel', '-'),
            groupdict.get('end', '-')
        )
        return [feat]


def paginated_url(url, params, offset, limit):
    new_params = [
        (key, val) for (key, val) in params
        if key != 'offset' and key != 'limit'
    ] + [('offset', offset), ('limit', limit)]
    return make_query_url(url, new_params)


def make_paginated_view(url, params, offset, limit, more):
    prev_offset = max(0, offset - limit)
    next_offset = offset + limit
    pager = {
        '@id': paginated_url(url, params, offset, limit),
        'firstPage': paginated_url(url, params, 0, limit),
        'paginatedProperty': 'edges'
    }
    if offset > 0:
        pager['previousPage'] = paginated_url(url, params, prev_offset, limit)
    if more:
        pager['nextPage'] = paginated_url(url, params, next_offset, limit)
    return pager


def lookup_grouped_by_feature(finder, term, scan_limit=200, group_limit=10):
    """
    Given a query for a concept, return assertions about that concept grouped by
    their features (for example, "A dog wants to ..." could be a group).

    It will scan up to `scan_limit` assertions to find out which features exist,
    then retrieve `group_limit` assertions for each feature if possible.
    """
    groups = defaultdict(list)
    more = set()
    if not term.startswith('/c/'):
        return error(
            {}, 400,
            'Only concept nodes (starting with /c/) can be grouped by feature.'
        )

    for assertion in finder.lookup(term, limit=scan_limit):
        groupkeys = []
        start = uri_prefix(assertion['start'])
        rel = assertion['rel']
        end = uri_prefix(assertion['end'])
        symmetric = rel in SYMMETRIC_RELATIONS
        if symmetric:
            groupkeys.append((('rel', rel), ('node', uri_prefix(term))))
        else:
            if field_match(assertion['start'], term):
                groupkeys.append((('rel', rel), ('start', start)))
            if field_match(assertion['end'], term):
                groupkeys.append((('rel', rel), ('end', end)))
        for groupkey in groupkeys:
            if len(groups[groupkey]) < group_limit:
                groups[groupkey].append(assertion)
            else:
                more.add(groupkey)

    for groupkey in groups:
        if len(groups[groupkey]) < group_limit:
            num_more = group_limit - len(groups[groupkey])
            for feature in groupkey_to_features(groupkey):
                # TODO: alternate between features when there are
                # multiple possibilities?
                for assertion in finder.lookup(feature, limit=num_more):
                    groups[groupkey].append(assertion)

    grouped = []
    for groupkey in groups:
        base_url = '/query'
        url = make_query_url(base_url, groupkey)
        assertions = groups[groupkey]
        symmetric = 'node' in dict(groupkey)
        group = {
            '@id': url,
            'weight': sum(assertion['weight'] for assertion in assertions),
            'edges': assertions,
            'symmetric': symmetric
        }
        if groupkey in more:
            view = make_paginated_view(base_url, groupkey, 0, group_limit, more=True)
            group['view'] = view
        grouped.append(group)

    grouped.sort(key=lambda g: -g['weight'])
    for group in grouped:
        del group['weight']

    response = {
        '@context': CONTEXT,
        '@id': term,
        'features': grouped
    }
    if not grouped:
        return error(response, 404, '%r is not a node in ConceptNet.' % term)
    else:
        return success(response)


def lookup_paginated(finder, term, offset=0, limit=50):
    # Query one more edge than asked for, so we know if there are more
    found = list(itertools.islice(finder.lookup(term), offset, offset + limit + 1))
    edges = found[:limit]
    response = {
        '@context': CONTEXT,
        '@id': term,
        'edges': edges
    }
    more = len(found) > len(edges)
    if len(found) > len(edges) or offset != 0:
        response['view'] = make_paginated_view(
            term, (), offset, limit, more=more
        )
    if not found:
        return error(response, 404, '%r is not a node in ConceptNet.' % term)
    else:
        return success(response)


def query_paginated(finder, query, offset=0, limit=50):
    found = finder.query(query, limit=limit + 1, offset=offset, scan_limit=limit * 4)
    edges = found[:limit]
    response = {
        '@context': CONTEXT,
        '@id': make_query_url('/query', query),
        'edges': edges
    }
    more = len(found) > len(edges)
    if len(found) > len(edges) or offset != 0:
        response['view'] = make_paginated_view(
            '/query', sorted(query.items()), offset, limit, more=more
        )
    return success(response)


def standardize_uri(language, text):
    """
    Look up the URI for a given piece of text. 'text' and 'language' should be
    given as parameters.
    """
    if text is None or language is None:
        return error({}, 400, "You should include the 'text' and 'language' parameters.")

    text = text.replace('_', ' ')
    uri = standardized_concept_uri(language, text)
    response = {
        '@id': uri
    }
    return success(response)
