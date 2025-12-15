from urllib.parse import urlparse
from pygments.lexers import get_lexer_for_filename
from pygments.util import ClassNotFound


def guess_language_by_extension(url, languages):
    """
    Given a URL file path and a list of languages, returns the matching
    language from the list, or None if no such match exists.
    See https://pygments.org/languages/ ("Short names")
    for a list of guessable languages.
    """
    parsed_url = urlparse(url)
    try:
        lexer = get_lexer_for_filename(parsed_url.path)
    except ClassNotFound:
        return None

    return next(
        (alias for alias in languages if alias in lexer.aliases),
        None
    )

