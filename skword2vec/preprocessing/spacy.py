from typing import Any, Iterable, Literal, Optional

from sklearn.base import TransformerMixin
from spacy.language import Language
from spacy.matcher import Matcher
from spacy.tokens import Doc, Token

# We create a new extension on tokens.
if not Token.has_extension("filter_pass"):
    Token.set_extension("filter_pass", default=False)

ALPHA_STOP_PATTERN = [[{"IS_ALPHA": True, "IS_STOP": False}]]


class SpacyPreprocessor(TransformerMixin):
    """Sklearn pipeline component to preprocess texts with a spaCy pipeline.

    Parameters
    ----------
    nlp: Language
        Spacy NLP pipeline.
    patterns: list of list of dict or None, default None
        List of patterns of tokens to accept and propagate.
        Patterns follow spaCy's Matcher syntax
        (https://spacy.io/usage/rule-based-matching#matcher)
        Every token that is part of a matching pattern will be passed
        forward, all others will be discarded.
        If not specified, only alphabetical tokens are allowed and
        stop words get removed.
    out_attribute: {'ORTH', 'NORM', 'LEMMA'}, default 'NORM'
        Attribute of the token to return as the textual representation.
    sentencize: bool, default False
        Determines whether the document should be split into sentences.
    n_jobs: int, default 1
        Number of cores to use for preprocessing with spaCy.
        -1 stands for all cores.
    """

    def __init__(
        self,
        nlp: Language,
        patterns: Optional[list[list[dict[str, Any]]]] = None,
        out_attribute: Literal["ORTH", "NORM", "LEMMA"] = "NORM",
        sentencize: bool = False,
        n_jobs: int = 1,
    ):
        self.nlp = nlp
        if patterns is not None:
            self.patterns = patterns
        else:
            self.patterns = ALPHA_STOP_PATTERN
        self.out_attribute = out_attribute
        self.matcher = Matcher(nlp.vocab)
        self.matcher.add("FILTER_PASS", patterns=self.patterns)
        self.sentencize = sentencize
        self.n_jobs = n_jobs

    def fit(self, X, y=None):
        """Exists for compatiblity, doesn't do anything."""
        return self

    def partial_fit(self, X, y=None):
        """Exists for compatiblity, doesn't do anything."""
        return self

    def label_matching_tokens(self, docs: list[Doc]):
        """Labels tokens that match one of the given patterns."""
        for doc in docs:
            matches = self.matcher(doc)
            for _, start, end in matches:
                for token in doc[start:end]:
                    token._.set("filter_pass", True)

    def token_to_str(self, token: Token) -> str:
        """Returns textual representation of token."""
        if self.out_attribute == "ORTH":
            return token.orth_
        elif self.out_attribute == "NORM":
            return token.norm_
        elif self.out_attribute == "LEMMA":
            return token.lemma_
        else:
            raise ValueError(
                """Unrecognized `out_attribute`.
                Please chose one of `"ORTH", "NORM", "LEMMA"`"""
            )

    def transform(self, X: Iterable[str]) -> list[list[list[str]]]:
        """Preprocesses document with a spaCy pipeline.

        Parameters
        ----------
        X: iterable of str
            Stream of documents.

        Returns
        -------
        list of list of list of str
            List of documents represented as list of sentences
            represented as lists of tokens.
        """
        docs = list(self.nlp.pipe(X, n_process=self.n_jobs))
        # Label all tokens according to the patterns.
        self.label_matching_tokens(docs)
        res: list[list[list[str]]] = []
        for doc in docs:
            doc_res: list[list[str]] = []
            # We act as if the entire doc was one sentence
            # if sentencize is false.
            sents = doc.sents if self.sentencize else [doc]
            for sent in sents:
                # We collect the textual representation of
                # all tokens that pass the filter.
                sent_tokens = [
                    self.token_to_str(token)
                    for token in sent
                    if token._.filter_pass
                ]
                doc_res.append(sent_tokens)
            res.append(doc_res)
        return res
