from database_creation.utils import BaseClass, Entity, Context
from database_creation.sentence import Sentence
from database_creation.coreference import Coreference

from xml.etree import ElementTree
from collections import defaultdict
from copy import deepcopy


class Article(BaseClass):
    # region Class initialization

    to_print = ['entities', 'title', 'date', 'abstract', 'contexts']
    print_attribute, print_lines, print_offsets = True, 1, 0

    def __init__(self, original_path, annotated_path):
        """
        Initializes an instance of Article.

        Args:
            original_path: str, path of the article's original corpus' content.
            annotated_path: str, path of the article's annotated corpus' content.
        """

        self.original_path = original_path
        self.annotated_path = annotated_path

        self.title = None
        self.date = None
        self.abstract = None

        self.entities = None

        self.sentences = None
        self.coreferences = None
        self.contexts = None

    # endregion

    # region Methods compute_

    def compute_metadata(self):
        """ Compute the metadata (title, date, abstract, entities) of the article. """

        root = ElementTree.parse(self.original_path).getroot()

        title = self.title or self.get_title(root)
        date = self.date or self.get_date(root)
        abstract = self.abstract or self.get_abstract(root)

        self.title = title
        self.date = date
        self.abstract = abstract

    def compute_annotations(self):
        """ Compute the annotations (sentences, coreferences) of the article. """

        if self.entities is None:
            self.entities = self.get_entities()

        root = ElementTree.parse(self.annotated_path).getroot()

        sentences = self.sentences or self.get_sentences(root)
        coreferences = self.coreferences or self.get_coreferences(root)

        self.sentences = sentences
        self.coreferences = coreferences

    def compute_contexts(self, tuple_, types):
        """
        Compute the contexts of the article for the Tuple of entities, according to the specified context types.

        Args:
            tuple_: Tuple, tuple of Entities mentioned in the article.
            types: set, set of strings, types of the context to compute.
        """

        name = tuple_.get_name()

        self.contexts = self.contexts or dict()
        self.contexts[name] = dict()

        for type_ in types:
            contexts = getattr(self, 'contexts_' + type_)(tuple_)

            for context_id_, context in contexts.items():
                self.contexts[name][context_id_] = context

    # endregion

    # region Methods get_

    @staticmethod
    def get_title(root):
        """
        Returns the title of an article given the tree of its metadata.

        Args:
            root: ElementTree.root, root of the metadata of the article.

        Returns:
            str, title of the article.
        """

        return root.find('./head/title').text

    @staticmethod
    def get_date(root):
        """
        Returns the date of an article given the tree of its metadata.

        Args:
            root: ElementTree.root, root of the metadata of the article.

        Returns:
            str, date of the article.
        """

        d = root.find('./head/meta[@name="publication_day_of_month"]').get('content')
        m = root.find('./head/meta[@name="publication_month"]').get('content')
        y = root.find('./head/meta[@name="publication_year"]').get('content')

        d = '0' + d if len(d) == 1 else d
        m = '0' + m if len(m) == 1 else m

        return '/'.join([y, m, d])

    @staticmethod
    def get_abstract(root):
        """
        Returns the abstract of an article given the tree of its metadata.

        Args:
            root: ElementTree.root, root of the metadata of the article.

        Returns:
            str, abstract of the article.
        """

        abstract = root.find('./body/body.head/abstract/p').text
        abstract = abstract.replace(' (M)', '').replace(' (L)', '').replace(' (S)', '')

        abstract = abstract.split('; ')
        while abstract[-1] in ['photo', 'photos', 'portrait', 'portraits', 'map', 'maps']:
            abstract = abstract[:-1]

        abstract = '; '.join(abstract)

        return abstract

    def get_entities(self):
        """
        Returns the Entities of the article given the tree of its metadata.

        Returns:
            set, Entities of the article.
        """

        root = ElementTree.parse(self.original_path).getroot()

        locations = [Entity(entity.text, 'location')
                     for entity in root.findall('./head/docdata/identified-content/location')]
        persons = [Entity(entity.text, 'person') for entity in root.findall('./head/docdata/identified-content/person')]
        orgs = [Entity(entity.text, 'org') for entity in root.findall('./head/docdata/identified-content/org')]

        entities = set(locations + persons + orgs)

        return entities

    @staticmethod
    def get_sentences(root):
        """
        Returns the Sentences of an article given the tree of its metadata.

        Args:
            root: ElementTree.root, root of the metadata of the article.

        Returns:
            dict, Sentences of the article (mapped with their indexes).
        """

        elements = root.findall('./document/sentences/sentence')
        sentences = {int(element.attrib['id']): Sentence(element) for element in elements}

        return sentences

    def get_coreferences(self, root):
        """
        Returns the Coreferences of an article given the tree of its metadata.

        Args:
            root: ElementTree.root, root of the metadata of the article.

        Returns:
            list, Coreferences of the article.
        """

        elements = root.findall('./document/coreference/coreference')
        coreferences = [Coreference(element, self.entities) for element in elements]

        return coreferences

    def get_entity_sentences(self, entity):
        """
        Returns the indexes of the sentences where there is a mention of the specified entity.

        Args:
            entity: Entity, entity we want to find mentions of.

        Returns:
            list, sorted list of sentences' indexes.
        """

        entity_sentences = set()

        for coreference in self.coreferences:
            if coreference.entity and entity.match(coreference.entity):
                entity_sentences.update(coreference.sentences)

        return sorted(entity_sentences)

    # endregion

    # region Methods criterion_

    def criterion_data(self):
        """
        Check if an article's data is complete, ie if its annotation file exists.

        Returns:
            bool, True iff the article's data is incomplete.
        """

        try:
            f = open(self.annotated_path, 'r')
            f.close()
            return False

        except FileNotFoundError:
            return True

    def criterion_entity(self):
        """
        Check if an article has at least 2 entities of the same type.

        Returns:
            bool, True iff the article hasn't 2 entities of the same type.
        """

        numbers = {'location': 0, 'person': 0, 'organization': 0}
        for entity in self.entities:
            numbers[entity.type_] += 1

        return True if max([numbers[type_] for type_ in numbers]) < 2 else False

    # endregion

    # region Methods contexts_

    def contexts_neigh_sent(self, tuple_):
        """
        Returns the neighboring-sentences contexts for a Tuple (neighboring sentences where the entities are mentioned).

        Args:
            tuple_: Tuple, entities to analyse.

        Returns:
            dict, neighbouring-sentences Contexts of the entities, mapped with their sentences span (indexes of the
            first and last sentences separated by '_').
        """

        sentences_entities = defaultdict(set)

        for i in range(len(tuple_.entities)):
            for idx in self.get_entity_sentences(tuple_.entities[i]):
                sentences_entities[idx].add(i)

        contexts_sentences = set()

        for idx in sentences_entities:
            unseens = list(range(len(tuple_.entities)))
            seers = set()

            for i in range(len(tuple_.entities)):
                if idx + i in sentences_entities:
                    for j in sentences_entities[idx + i]:
                        try:
                            unseens.remove(j)
                            seers.add(idx + i)
                        except ValueError:
                            pass

                    if not unseens:
                        seers = sorted(seers)
                        contexts_sentences.add(tuple(range(seers[0], seers[-1] + 1)))
                        break

        contexts_sentences = sorted(contexts_sentences)
        contexts = dict()

        for idxs in contexts_sentences:
            entity_coreferences = {}
            for idx in idxs:
                correspondences = []

                for entity in tuple_.entities:
                    correspondence = [coreference for coreference in self.coreferences if idx in coreference.sentences
                                      and coreference.entity and coreference.entity == entity.name]

                    correspondences.append(tuple([entity, correspondence]))

                entity_coreferences[idx] = correspondences

            id_ = str(idxs[0]) + '_' + str(idxs[-1])
            contexts[id_] = Context(sentences={idx: deepcopy(self.sentences[idx]) for idx in idxs},
                                    entity_coreferences=entity_coreferences)

        return contexts

    # TODO: put in bold the entities in the abstract
    def contexts_abstract(self, tuple_):
        """
        Returns the abstract contexts for a Tuple (abstract if the entities are mentioned).

        Args:
            tuple_: Tuple, entities to analyse.

        Returns:
            dict, abstract Context of the entities, mapped with its id_ (which is '0').
        """

        contexts = dict()

        for entity in tuple_.entities:
            if not entity.is_in(string=self.abstract, flexible=True):
                return contexts

        contexts['0'] = Context(abstract=self.abstract)

        return contexts

    # endregion


def main():
    from database_creation.utils import Tuple

    article = Article('../databases/nyt_jingyun/data/2000/01/01/1165027.xml',
                      '../databases/nyt_jingyun/content_annotated/2000content_annotated/1165027.txt.xml')

    article.compute_metadata()
    article.compute_annotations()
    article.compute_contexts(tuple_=Tuple(id_='0', entities=tuple(article.entities)),
                             types=['abstract', 'neigh_sent'])

    print(article)
    return


if __name__ == '__main__':
    main()
