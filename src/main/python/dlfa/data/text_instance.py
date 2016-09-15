from typing import List

from overrides import overrides

from .constants import SHIFT_OP, REDUCE2_OP, REDUCE3_OP
from .instance import Instance
from .indexed_instance import IndexedInstance
from .indexed_instance import IndexedTrueFalseInstance
from .indexed_instance import IndexedBackgroundInstance
from .indexed_instance import IndexedLogicalFormInstance
from .indexed_instance import IndexedQuestionInstance
from .tokenizer import tokenizers, Tokenizer
from .data_indexer import DataIndexer


class TextInstance(Instance):
    """
    An Instance that has some attached text, typically either a sentence or a logical form. Calling
    this a "TextInstance" is because the individual tokens here are encoded as strings, and we can
    get a list of strings out when we ask what words show up in the instance.

    We use these kinds of instances to fit a DataIndexer (e.g., deciding which words should be
    mapped to an unknown token); to use them in training or testing, we need to first convert them
    into IndexedInstances.
    """
    def __init__(self,
                 label,
                 index: int=None,
                 tokenizer: Tokenizer=tokenizers['default']()):
        super(TextInstance, self).__init__(label, index)
        self.tokenizer = tokenizer

    def _tokenize(self, sentence: str) -> List[str]:
        return self.tokenizer.tokenize(sentence)

    def words(self) -> List[str]:
        """
        Returns a list of all of the words in this instance.  This is mainly used for computing
        word counts when fitting a word vocabulary on a dataset.
        """
        raise NotImplementedError

    def to_indexed_instance(self, data_indexer: DataIndexer) -> IndexedInstance:
        """
        Converts the words in this Instance into indices using the DataIndexer.
        """
        raise NotImplementedError

class TrueFalseInstance(TextInstance):
    def __init__(self,
                 text: str,
                 label: bool,
                 index: int=None,
                 tokenizer: Tokenizer=tokenizers['default']()):
        """
        text: the text of this instance, typically either a sentence or a logical form.
        """
        super(TrueFalseInstance, self).__init__(label, index, tokenizer)
        self.text = text

    @overrides
    def words(self) -> List[str]:
        return self._tokenize(self.text.lower())

    @overrides
    def to_indexed_instance(self, data_indexer: DataIndexer):
        indices = [data_indexer.get_word_index(word) for word in self.words()]
        return IndexedTrueFalseInstance(indices, self.label, self.index)

    @classmethod
    def read_from_line(cls,
                       line: str,
                       default_label: bool=None,
                       tokenizer: Tokenizer=tokenizers['default']()):
        """
        Reads a TrueFalseInstance object from a line.  The format has one of four options:

        (1) [sentence]
        (2) [sentence index][tab][sentence]
        (3) [sentence][tab][label]
        (4) [sentence index][tab][sentence][tab][label]

        For options (1) and (2), we use the default_label to give the Instance a label, and for
        options (3) and (4), we check that default_label matches the label in the file, if
        default_label is given.

        The reason we check for a match between the read label and the default label in cases (3)
        and (4) is that if you passed a default label, you should be confident that everything
        you're reading has that label.  If we find one that doesn't match, you probably messed up
        some parameters somewhere else in your code.
        """
        fields = line.split("\t")

        # We'll call Instance._check_label for all four cases, even though it means passing None to
        # two of them.  We do this mainly for consistency, and in case the _check_label() ever
        # changes to actually do something with the label=None case.
        if len(fields) == 3:
            index, text, label_string = fields
            label = label_string == '1'
            cls._check_label(label, default_label)
            return cls(text, label, int(index), tokenizer)
        elif len(fields) == 2:
            if fields[0].isdecimal():
                index, text = fields
                cls._check_label(None, default_label)
                return cls(text, default_label, int(index), tokenizer)
            elif fields[1].isdecimal():
                text, label_string = fields
                label = label_string == '1'
                cls._check_label(label, default_label)
                return cls(text, label, tokenizer=tokenizer)
            else:
                raise RuntimeError("Unrecognized line format: " + line)
        elif len(fields) == 1:
            text = fields[0]
            cls._check_label(None, default_label)
            return cls(text, default_label, tokenizer=tokenizer)
        else:
            raise RuntimeError("Unrecognized line format: " + line)


class LogicalFormInstance(TrueFalseInstance):
    """
    This is an instance for use with TreeLSTMs.  Instead of a sequence of words, this Instance is a
    tree-structured logical form, encoded as something like "for(depend_on(human, plant), oxygen)".
    """
    @overrides
    def words(self) -> List[str]:
        """
        This method takes all predicate names and arguments and returns them, removing commas and
        parentheses.
        """
        return [word for word in self.tokens() if word != ',' and word != ')' and word != '(']

    def tokens(self) -> List[str]:
        """
        This method splits the logical form into tokens, including commas and parentheses.
        """
        raise NotImplementedError

    @overrides
    def to_indexed_instance(self, data_indexer: DataIndexer):
        """
        Here we have to split the logical forms (containing parantheses and commas) into two
        sequences, one containing only elements (predicates and arguments) and the other containing
        shift and reduce operations.

        Example:
        self.text: "a(b(c), d(e, f))"
        Outputs: ['a', 'b', 'c', 'd', 'e', 'f']; [S, S, S, R2, S, S, S, R3, R3]

        (except the real output passes the elements through the data indexer as well)
        """
        last_symbols = []  # Keeps track of commas and open parens
        transitions = []
        elements = []
        is_malformed = False
        for token in self.tokens():
            if token == ',':
                last_symbols.append(token)
            elif token == '(':
                last_symbols.append(token)
            elif token == ')':
                if len(last_symbols) == 0:
                    # This means we saw a closing paren without an opening paren.
                    is_malformed = True
                    break
                last_symbol = last_symbols.pop()
                if last_symbol == '(':
                    transitions.append(REDUCE2_OP)
                else:
                    # Last symbol is a comma. Pop the open paren before it as well.
                    last_symbols.pop()
                    transitions.append(REDUCE3_OP)
            else:
                # The token is a predicate or an argument.
                transitions.append(SHIFT_OP)
                elements.append(token)
        if len(last_symbols) != 0 or is_malformed:
            raise RuntimeError("Malformed binary semantic parse: %s" % self.text)
        indices = [data_indexer.get_word_index(word) for word in elements]
        return IndexedLogicalFormInstance(indices, transitions, self.label, self.index)


class BackgroundInstance(TextInstance):
    """
    An Instance that has background knowledge associated with it.  That background knowledge can
    currently only be expressed as a list of sentences.  Maybe someday we'll expand that to allow
    other kinds of background knowledge.
    """
    def __init__(self, instance: TextInstance, background: List[str]):
        super(BackgroundInstance, self).__init__(instance.label, instance.index, instance.tokenizer)
        self.instance = instance
        self.background = background

    @overrides
    def words(self):
        words = []
        words.extend(self.instance.words())
        for background_text in self.background:
            words.extend(self._tokenize(background_text.lower()))
        return words

    @overrides
    def to_indexed_instance(self, data_indexer: DataIndexer):
        indexed_instance = self.instance.to_indexed_instance(data_indexer)
        background_indices = []
        for text in self.background:
            words = self._tokenize(text.lower())
            indices = [data_indexer.get_word_index(word) for word in words]
            background_indices.append(indices)
        return IndexedBackgroundInstance(indexed_instance, background_indices)


class QuestionInstance(TextInstance):
    """
    A QuestionInstance is a grouping of other Instances, where exactly one of those Instance must
    have label True.  When this is converted to training data, it will group all of those option
    Instances into a single training instance, with a label that is an index to the answer option
    that is correct for its label.
    """
    def __init__(self, options: List[TextInstance]):
        self.options = options
        positive_index = [index for index, instance in enumerate(options) if instance.label is True]
        assert len(positive_index) == 1
        label = positive_index[0]
        tokenizer = self.options[0].tokenizer if self.options else None
        super(QuestionInstance, self).__init__(label, None, tokenizer)

    @overrides
    def words(self):
        words = []
        for option in self.options:
            words.extend(option.words())
        return words

    @overrides
    def to_indexed_instance(self, data_indexer: DataIndexer):
        indexed_options = [option.to_indexed_instance(data_indexer) for option in self.options]
        return IndexedQuestionInstance(indexed_options, self.label)
