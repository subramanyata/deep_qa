# pylint: disable=no-self-use,invalid-name
import numpy

# pylint: disable=line-too-long
from deep_qa.data.instances.text_classification.text_classification_instance import IndexedTextClassificationInstance
from deep_qa.data.instances.text_classification.text_classification_instance import TextClassificationInstance
# pylint: enable=line-too-long
from ....common.test_case import DeepQaTestCase


class TestTextClassificationInstance:
    @staticmethod
    def instance_to_line(text, label=None, index=None):
        line = ''
        if index is not None:
            line += str(index) + '\t'
        line += text
        if label is not None:
            label_str = '1' if label else '0'
            line += '\t' + label_str
        return line

    def test_read_from_line_handles_one_column(self):
        text = "this is a sentence"
        instance = TextClassificationInstance.read_from_line(text)
        assert instance.text == text
        assert instance.label is None
        assert instance.index is None

    def test_read_from_line_handles_three_column(self):
        index = 23
        text = "this is a sentence"
        label = True
        line = self.instance_to_line(text, label, index)

        instance = TextClassificationInstance.read_from_line(line)
        assert instance.text == text
        assert instance.label is label
        assert instance.index == index

    def test_read_from_line_handles_two_column_with_label(self):
        index = None
        text = "this is a sentence"
        label = True
        line = self.instance_to_line(text, label, index)

        instance = TextClassificationInstance.read_from_line(line)
        assert instance.text == text
        assert instance.label is label
        assert instance.index == index

    def test_read_from_line_handles_two_column_with_index(self):
        index = 23
        text = "this is a sentence"
        label = None
        line = self.instance_to_line(text, label, index)

        instance = TextClassificationInstance.read_from_line(line)
        assert instance.text == text
        assert instance.label is label
        assert instance.index == index

    def test_words_tokenizes_the_sentence_correctly(self):
        t = TextClassificationInstance("This is a sentence.", None)
        assert t.words() == {'words': ['this', 'is', 'a', 'sentence', '.']}
        t = TextClassificationInstance("This isn't a sentence.", None)
        assert t.words() == {'words': ['this', 'is', "n't", 'a', 'sentence', '.']}
        t = TextClassificationInstance("And, I have commas.", None)
        assert t.words() == {'words': ['and', ',', 'i', 'have', 'commas', '.']}


class TestIndexedTextClassificationInstance(DeepQaTestCase):
    def test_get_padding_lengths_returns_length_of_word_indices(self):
        instance = IndexedTextClassificationInstance([1, 2, 3, 4], True)
        assert instance.get_padding_lengths() == {'num_sentence_words': 4}

    def test_pad_adds_zeros_on_left(self):
        instance = IndexedTextClassificationInstance([1, 2, 3, 4], True)
        instance.pad({'num_sentence_words': 5})
        assert instance.word_indices == [0, 1, 2, 3, 4]

    def test_pad_truncates_from_right(self):
        instance = IndexedTextClassificationInstance([1, 2, 3, 4], True)
        instance.pad({'num_sentence_words': 3})
        assert instance.word_indices == [2, 3, 4]

    def test_as_training_data_produces_correct_numpy_arrays(self):
        instance = IndexedTextClassificationInstance([1, 2, 3, 4], True)
        inputs, label = instance.as_training_data()
        assert numpy.all(label == numpy.asarray([0, 1]))
        assert numpy.all(inputs == numpy.asarray([1, 2, 3, 4]))
        instance.label = False
        _, label = instance.as_training_data()
        assert numpy.all(label == numpy.asarray([1, 0]))
