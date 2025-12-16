from urllib.parse import urlparse
from pygments.lexers import get_lexer_for_filename
from pygments.util import ClassNotFound

'''
This is currently just a list of languages supported
by our syntax highlighter, Highlight.js, *without plaintext.*
You can regenerate this list by loading up the site,
opening a JS REPL in the browser's dev tools,
and executing `hljs.listLanguanges()`.

CDDL is an IETF schema language so it is added.  We may eventually need some logic so that we
can less tightly connect what file extension something is to what we tell the highlighter what to use.

Note that the actual allowlist is an intersection
of this list and the lexers from pygments.
'''
SPECIFICATION_LANGUAGE_ALLOWLIST = [
"bash","c","cpp","csharp","css","diff","go","graphql","ini","java","javascript","json","kotlin","less","lua","makefile","markdown","objectivec","perl","php","php-template","python","python-repl","r","ruby","rust","scss","shell","sql","swift","typescript","vbnet","wasm","xml","yaml","cddl"
]


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


def guess_specification_language_by_extension(url):
    """
    Given a URL file path, returns the matching language from a list
    of allowed specification languages, or None if no such match exists.
    """
    return guess_language_by_extension(url, SPECIFICATION_LANGUAGE_ALLOWLIST)

