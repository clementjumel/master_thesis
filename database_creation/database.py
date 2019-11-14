from database_creation.utils import Tuple, Wikipedia, Query, Result
from database_creation.article import Article

from numpy.random import shuffle, seed
from time import time
from glob import glob
from collections import defaultdict
from pickle import dump, load, PicklingError
from pandas import DataFrame, read_csv
from unidecode import unidecode
from wikipedia import search, page, WikipediaException, DisambiguationError

import matplotlib.pyplot as plt


class Database:
    # region Class initialization

    modulo_articles, modulo_tuples, modulo_entities = 500, 1000, 100

    def __init__(self, years=(2006, 2007), max_size=None, shuffle=True, min_articles=1, min_queries=1, random_seed=0):
        """
        Initializes an instance of Database.

        Args:
            years: list, years (int) of the database to analyse.
            max_size: int, maximum number of articles in the database; if None, takes all articles.
            shuffle: bool, whether to shuffle the articles selected in the database.
            min_articles: int, minimum number of articles an entities' tuple must be in.
            min_queries: int, minimum number of Queries an entities' tuple must have.
            random_seed: int, the seed to use for the random processes.
        """

        self.years = years
        self.max_size = max_size
        self.shuffle = shuffle
        self.min_articles = min_articles
        self.min_queries = min_queries
        self.random_seed = random_seed

        self.articles = None
        self.entities = None
        self.tuples = None
        self.wikipedia = None
        self.queries = None
        self.stats = None
        self.tasks = None
        self.results = None

        seed(random_seed)

    def __str__(self):
        """
        Overrides the builtin str method, customized for the instances of Database.

        Returns:
            str, readable format of the instance.
        """

        s = "Years: " + ', '.join([str(year) for year in self.years]) + '\n'
        s += "Max size: " + str(self.max_size) + '\n'
        s += "Shuffle: " + str(self.shuffle) + '\n'
        s += "Min articles: " + str(self.min_articles) + '\n'
        s += "Min queries: " + str(self.min_queries)

        return s

    # endregion

    # region Decorators

    class Verbose:
        """ Decorator for the display of a simple message. """

        def __init__(self, message):
            """ Initializes the Verbose decorator message. """

            self.message = message

        def __call__(self, func):
            """ Performs the call to the decorated function. """

            def f(*args, **kwargs):
                """ Decorated function. """

                t0 = time()

                print(self.message)
                func(*args, **kwargs)
                print("Done (elapsed time: {}s).\n".format(round(time() - t0)))

            return f

    class Attribute:
        """ Decorator for monitoring the length of an attribute. """

        def __init__(self, attribute):
            """ Initializes the Attribute decorator attribute. """

            self.attribute = attribute

        def __call__(self, func):
            """ Performs the call to the decorated function. """

            def f(*args, **kwargs):
                """ Decorated function. """

                slf = args[0]

                attribute = getattr(slf, self.attribute)
                length = len(attribute) if attribute is not None else 0
                print("Initial length of {}: {}".format(self.attribute, length))

                func(*args, **kwargs)

                attribute = getattr(slf, self.attribute)
                length = len(attribute) if attribute is not None else 0
                print("Final length of {}: {}".format(self.attribute, length))

            return f

    # endregion

    # region Main methods

    @Verbose("Preprocessing the database...")
    def preprocess_database(self, debug=False):
        """
        Performs the preprocessing of the database.

        Args:
            debug: bool, whether or not to perform the debugging of the database.
        """

        self.compute_articles(debug=debug)

        self.clean_articles(criterion=Article.criterion_content)

        self.compute_metadata(debug=debug)
        self.compute_entities(debug=debug)
        self.compute_tuples(debug=debug)

        self.filter(min_articles=self.min_articles)

    @Verbose("Preprocessing the articles...")
    def process_articles(self, debug=False):
        """
        Performs the preprocessing of the articles.

        Args:
            debug: bool, whether or not to perform the debugging of the database.
        """

        self.compute_annotations(debug=debug)
        self.compute_contexts(debug=debug)

        self.filter(min_queries=self.min_queries)

    @Verbose("Processing the wikipedia information...")
    def process_wikipedia(self, load=False, file_name=None, debug=False):
        """
        Performs the processing of the wikipedia information of the database.

        Args:
            load: bool, if True, load an existing file.
            file_name: str, name of the wikipedia file to save or load; if None, deal with the standard files name.
            debug: bool, whether or not to perform the debugging of the database.
        """

        self.load_pkl(attribute_name='wikipedia', file_name=file_name, folder_name='wikipedia') if load else None
        self.compute_wikipedia(load=load, debug=debug)
        self.save_pkl(attribute_name='wikipedia', file_name=file_name, folder_name='wikipedia')

    @Verbose("Processing the aggregation queries...")
    def process_queries(self, load=False, check_changes=False, file_name=None, debug=False, csv_seed=1):
        """
        Performs the processing of the aggregation queries.

        Args:
            load: bool, if True, load an existing file.
            check_changes: bool, if not load, load the existing queries file and check if there are changes in the new.
            file_name: str, name of the wikipedia file to save or load; if None, deal with the standard files name.
            debug: bool, whether or not to perform the debugging of the database.
            csv_seed: int, the seed to use for the random processes.
        """

        if load:
            self.load_pkl(attribute_name='queries', file_name=file_name)

        else:
            if check_changes:
                try:
                    self.load_pkl(attribute_name='queries', file_name=file_name)
                except FileNotFoundError:
                    check_changes = False
                    print("Unable to check the changes: the queries file is missing.")
            old_queries = self.queries

            self.compute_queries(debug=debug)
            self.save_pkl(attribute_name='queries', file_name=file_name)
            self.save_csv(attribute_name='queries', file_name=file_name, limit=100, random_seed=csv_seed)

            if check_changes:
                if old_queries == self.queries:
                    print("\nNo change in the computed queries.")
                else:
                    print("\nThe queries have changed!")

    @Verbose("Processing the results...")
    def process_results(self):
        """ Process the results of an annotation task. """

        self.compute_tasks()
        self.compute_results()

    @Verbose("Computing and displaying statistics...")
    def process_stats(self, type_):
        """
        Compute and display the statistics of the database of the given type.

        Args:
            type_: str, type of the statistics, must be 'tuples', 'wikipedia' or 'contexts'.
        """

        getattr(self, 'compute_stats_' + type_)()
        getattr(self, 'display_stats_' + type_)()

    @Verbose("Combining the wikipedia files...")
    def combine_wiki(self, current=True, in_names=tuple(['wikipedia_global']), out_name='wikipedia_global'):
        """
        Combines current wikipedia information and some other wikipedia files into a single file. Note that the
        most up to date information should come from the last file form in_names.

        Args:
            current: bool, whether to use the current wikipedia information.
            in_names: list, names of the file to combine.
            out_name: str, name of the file to write in.
        """

        out_wikipedia = {'found': dict(), 'not_found': set()}

        if current:
            print("Current wikipedia information: {} found/{} not_found...".format(len(self.wikipedia['found']),
                                                                                   len(self.wikipedia['not_found'])))

            for type_ in ['found', 'not_found']:
                out_wikipedia[type_].update(self.wikipedia[type_])

            print("Global file updated: {} found/{} not_found.\n".format(len(out_wikipedia['found']),
                                                                         len(out_wikipedia['not_found'])))

        for in_name in in_names:
            in_wikipedia = self.load_pkl(file_name=in_name, folder_name='wikipedia')

            print("File {}: {} found/{} not_found...".format(in_name,
                                                             len(in_wikipedia['found']),
                                                             len(in_wikipedia['not_found'])))

            for type_ in ['found', 'not_found']:
                out_wikipedia[type_].update(in_wikipedia[type_])

            print("Global file updated: {} found/{} not_found.\n".format(len(out_wikipedia['found']),
                                                                         len(out_wikipedia['not_found'])))

        self.save_pkl(obj=out_wikipedia, file_name=out_name, folder_name='wikipedia')
        self.wikipedia = out_wikipedia

    @Verbose("Solving manually the wikipedia issues...")
    def correct_wiki(self, step, out_name=None):
        """
        Run the manual correction of the wikipedia tricky cases.

        Args:
            step: int, step of the correction to perform, between 1 and 4.
            out_name: str, name of the wikipedia file to save; if None, deal with the standard files name.
        """

        self.compute_correction(step=step)
        self.save_pkl(attribute_name='wikipedia', file_name=out_name, folder_name='wikipedia')

    # endregion

    # region Methods compute_

    @Verbose("Computing the database' article...")
    @Attribute('articles')
    def compute_articles(self, debug=False):
        """
        Computes and initializes the articles in the database.

        Args:
            debug: bool, whether or not to perform the debugging of the database.
        """

        articles = {}
        root = '../databases/nyt_jingyun/'

        for data_path in self.paths():
            id_ = data_path.split('/')[-1].split('.')[0]
            year = data_path.split('/')[-4]

            content_path = root + 'content_annotated/' + str(year) + 'content_annotated/' + id_ + '.txt.xml'
            summary_path = root + 'summary_annotated/' + str(year) + 'summary_annotated/' + id_ + '.txt.xml'

            articles[id_] = Article(data_path=data_path, content_path=content_path, summary_path=summary_path)

        self.articles = articles

        self.write_debug(field='articles', method='articles') if debug else None

    @Verbose("Computing the articles' metadata...")
    def compute_metadata(self, debug=False):
        """
        Computes the metadata of the articles.

        Args:
            debug: bool, whether or not to perform the debugging of the database.
        """

        count, size = 0, len(self.articles)
        for id_ in self.articles:
            count = self.progression(count, self.modulo_articles, size, 'article')
            self.articles[id_].compute_metadata()

        self.write_debug(field='articles', method='metadata') if debug else None

    @Verbose("Computing the database' entities...")
    @Attribute('entities')
    def compute_entities(self, debug=False):
        """
        Compute the entities of the database.

        Args:
            debug: bool, whether or not to perform the debugging of the database.
        """

        self.entities = dict()

        count, size = 0, len(self.articles)
        for _, article in self.articles.items():
            count = self.progression(count, self.modulo_articles, size, 'article')

            try:
                entities = article.get_entities()
            except AssertionError:
                print("      Several entities have the same name ({}); ignoring them...".format(
                    '; '.join(article.get_vanilla_entities())
                ))
                entities = []

            for entity in entities:
                if str(entity) in self.entities:
                    try:
                        self.entities[str(entity)].update_info(entity)
                    except AssertionError:
                        print("      {} corresponds to both {} and {}, ignoring the later...".format(
                            str(entity), entity.type_, self.entities[str(entity)].type_
                        ))
                else:
                    self.entities[str(entity)] = entity

            article.entities = [self.entities[name] for name in [str(entity) for entity in entities]]

        self.write_debug(field='articles', method='article_entities') if debug else None
        self.write_debug(field='entities', method='entities') if debug else None

    @Verbose("Computing the entity tuples...")
    @Attribute('tuples')
    def compute_tuples(self, debug=False):
        """
        Compute the Tuples of the database as a sorted list of Tuples (by number of articles).

        Args:
            debug: bool, whether or not to perform the debugging of the database.
        """

        ids = defaultdict(set)

        count, size = 0, len(self.articles)
        for id_ in self.articles:
            count = self.progression(count, self.modulo_articles, size, 'article')

            entities = defaultdict(set)
            for entity in self.articles[id_].entities:
                entities[entity.type_].add(entity.name)

            for type_ in entities:
                for tuple_ in self.subtuples(entities[type_]):
                    ids[tuple_].add(id_)

        ranking = sorted(ids, key=lambda k: (len(ids[k]), str(k)), reverse=True)

        self.tuples = [Tuple(id_=str(rank + 1),
                             entities=tuple([self.entities[name] for name in tuple_]),
                             article_ids=ids[tuple_])
                       for rank, tuple_ in enumerate(ranking)]

        self.write_debug(field='tuples', method='tuples') if debug else None

    @Verbose("Computing the articles' annotations...")
    def compute_annotations(self, debug=False):
        """
        Computes the annotations of the articles.

        Args:
            debug: bool, whether or not to perform the debugging of the database.
        """

        count, size = 0, len(self.articles)
        for id_ in self.articles:
            count = self.progression(count, self.modulo_articles, size, 'article')
            self.articles[id_].compute_annotations()

        self.write_debug(field='articles', method='annotations') if debug else None

    @Verbose("Computing the contexts...")
    def compute_contexts(self, debug=False):
        """
        Compute the contexts of the articles for each Tuple.

        Args:
            debug: bool, whether or not to perform the debugging of the database.
        """

        count, size = 0, len(self.tuples)
        for tuple_ in self.tuples:
            count = self.progression(count, self.modulo_tuples, size, 'tuple')
            query_ids = set()

            for article_id_ in tuple_.article_ids:
                self.articles[article_id_].compute_contexts(tuple_=tuple_)

                query_ids.update({tuple_.id_ + '_' + article_id_ + '_' + context_id_
                                  for context_id_ in self.articles[article_id_].contexts[str(tuple_)]})

            tuple_.query_ids = query_ids

        self.write_debug(field='articles', method='contexts') if debug else None

    @Verbose("Computing the Wikipedia information...")
    def compute_wikipedia(self, load, debug=False):
        """
        Compute the wikipedia information about the entities from self.tuples.

        Args:
            load: bool, if True, load an existing file.
            debug: bool, whether or not to perform the debugging of the database.
        """

        wikipedia = {'found': dict(), 'not_found': set()} if not load else self.wikipedia
        print("Initial found entries: {}/not found: {}".format(len(wikipedia['found']), len(wikipedia['not_found'])))

        try:
            count, size = 0, len(self.entities)
            for name, entity in self.entities.items():
                count = self.progression(count, self.modulo_entities, size, 'entity')

                if not load:
                    wiki = entity.get_wiki()
                    if wiki.summary is not None:
                        wikipedia['found'][name] = wiki
                    else:
                        wikipedia['not_found'].add(name)

                else:
                    if name in wikipedia['found']:
                        wiki = wikipedia['found'][name]
                    elif name in wikipedia['not_found']:
                        wiki = Wikipedia()
                    else:
                        wiki = entity.get_wiki()
                        if wiki.summary is not None:
                            wikipedia['found'][name] = wiki
                        else:
                            wikipedia['not_found'].add(name)

                entity.wiki = wiki

        except (KeyboardInterrupt, WikipediaException) as e:
            print("A known error occurred, saving the loaded information ({})...".format(e))

        print("Final found entries: {}/not found: {}".format(len(wikipedia['found']), len(wikipedia['not_found'])))
        self.wikipedia = wikipedia

        self.write_debug(field='wikipedia', method='wikipedia') if debug else None

    @Verbose("Computing the Queries...")
    @Attribute('queries')
    def compute_queries(self, debug=False):
        """
        Compute the Queries of the database.

        Args:
            debug: bool, whether or not to perform the debugging of the database.
        """

        queries = dict()

        count, size = 0, len(self.tuples)
        for tuple_ in self.tuples:
            count = self.progression(count, self.modulo_tuples, size, 'tuple')

            for article_id_ in sorted(tuple_.article_ids):
                article_contexts = self.articles[article_id_].contexts[str(tuple_)]

                for context_id_, context in article_contexts.items():
                    query_id_ = '_'.join([article_id_, tuple_.id_, context_id_])
                    queries[query_id_] = Query(id_=query_id_,
                                               tuple_=tuple_,
                                               article=self.articles[article_id_],
                                               context=context)

        self.queries = queries

        self.write_debug(field='queries', method='queries') if debug else None

    @Verbose("Computing the tasks...")
    @Attribute('tasks')
    def compute_tasks(self):
        """ Compute the tasks of the annotation. """

        tasks = dict()

        for path in glob('../pilot/*/task/*.pkl'):
            version = path.split('/')[2]
            folder_name, file_name = '/'.join(path.split('/')[:-1]), path.split('/')[-1].split('.pkl')[0]

            tasks[version] = self.load_pkl(file_name=file_name, folder_name=folder_name)

        self.tasks = tasks

    @Verbose("Computing the results...")
    @Attribute('results')
    def compute_results(self):
        """ Compute the results of an annotation task. """

        results = defaultdict(lambda: defaultdict(list))  # defaultdict of defaultdict of list

        for path in glob('../pilot/*/results/*.csv'):
            version = path.split('/')[2]
            df = read_csv(path)

            for _, row in df.iterrows():
                id_ = row.get('Input.id_')
                results[version][id_].append(Result(id_, version, row))

        self.results = results

    @Verbose("Computing the correction of the wikipedia information...")
    def compute_correction(self, step):
        """
        Performs the manual correction of the wikipedia information.

        Args:
            step: int, step of the correction to perform, starting with 0.
        """

        to_correct, corrected = set([name for name, wiki in self.wikipedia['found'].items() if not wiki.exact]), set()
        if not to_correct:
            print("All the {} entities are exact, no correction to be made...".format(len(self.wikipedia['found'])))
            return
        else:
            print("{} entities to correct (on {}).".format(len(to_correct), len(self.wikipedia['found'])))

        try:
            if step == 1:
                count, size = 0, len(to_correct)
                for name in sorted(to_correct):
                    count = self.progression(count, self.modulo_entities, size, 'to correct entity')

                    preprocessed_name_1 = unidecode(name).lower().replace('.', '')
                    preprocessed_name_2 = ' '.join([word for word in preprocessed_name_1.split() if len(word) > 1])

                    preprocessed_title_1 = unidecode(self.wikipedia['found'][name].title).lower().replace('.', '')
                    preprocessed_title_2 = ' '.join([word for word in preprocessed_title_1.split() if len(word) > 1])

                    if preprocessed_name_1 == preprocessed_title_1 or preprocessed_name_2 == preprocessed_title_2:
                        self.wikipedia['found'][name].exact = True
                        corrected.add(name)

                to_correct, corrected = to_correct.difference(corrected), set()
                print("First step over, still {} to correct (on {})".format(len(to_correct),
                                                                            len(self.wikipedia['found'])))

            if step == 2:
                count, size = 0, len(to_correct)
                for name in sorted(to_correct):
                    count = self.progression(count, self.modulo_entities, size, 'to correct entity')

                    while True:
                        answer = input(name + '/' + self.wikipedia['found'][name].title + ": is this good? [y/n/o]")
                        if answer in ['y', 'n', 'o']:
                            break
                        else:
                            print("Answer should be 'y', 'n' or 'o', try again.")

                    if answer == 'o':
                        while True:
                            answer = input(self.wikipedia['found'][name].get_info() + ": is this good? [y/n]")
                            if answer in ['y', 'n']:
                                break
                            else:
                                print("Answer should be 'y' or 'n', try again.")

                    if answer == 'y':
                        self.wikipedia['found'][name].exact = True
                        corrected.add(name)

                to_correct, corrected = to_correct.difference(corrected), set()
                print("Second step over, still {} to correct (on {})".format(len(to_correct),
                                                                             len(self.wikipedia['found'])))

            if step == 3:
                count, size = 0, len(to_correct)
                for name in sorted(to_correct):
                    count = self.progression(count, self.modulo_entities, size, 'to correct entity')

                    wiki_search = search(name)
                    print("Wikipedia search for {}:".format(name))
                    for cmpt, title in enumerate(wiki_search):
                        print(str(cmpt + 1) + ': ' + title)

                    while True:
                        try:
                            answer = int(input("Which number is the good one? (0 for no-one)"))
                            if answer in range(len(wiki_search) + 1):
                                break
                            else:
                                print("Answer should be between 0 and the length of the wikipedia search, try again.")
                        except ValueError:
                            print("Answer should be an int, try again.")

                    if answer != 0:
                        try:
                            p = page(wiki_search[answer - 1])
                            self.wikipedia['found'][name] = Wikipedia(p)

                        except DisambiguationError:
                            print("Search is still ambiguous, moving on...")

                to_correct, corrected = to_correct.difference(corrected), set()
                print("Third step over, still {} to correct (on {})".format(len(to_correct),
                                                                            len(self.wikipedia['found'])))

            if step == 4:
                count, size = 0, len(to_correct)
                for name in sorted(to_correct):
                    count = self.progression(count, self.modulo_entities, size, 'to correct entity')

                    while True:
                        answer = input(name + '/' + self.wikipedia['found'][name].title + ": discard? [y/n/o]")
                        if answer in ['y', 'n', 'o']:
                            break
                        else:
                            print("Answer should be 'y', 'n' or 'o', try again.")

                    if answer == 'o':
                        while True:
                            answer = input(self.wikipedia['found'][name].get_info() + ": discard? [y/n]")
                            if answer in ['y', 'n']:
                                break
                            else:
                                print("Answer should be 'y' or 'n', try again.")

                    if answer == 'y':
                        del self.wikipedia['found'][name]
                        self.wikipedia['not_found'].add(name)
                        corrected.add(name)

                to_correct, corrected = to_correct.difference(corrected), set()
                print("Fourth step over, still {} to correct (on {})".format(len(to_correct),
                                                                             len(self.wikipedia['found'])))

            if step == 5:
                count, size = 0, len(to_correct)
                for name in sorted(to_correct):
                    count = self.progression(count, self.modulo_entities, size, 'to correct entity')

                    del self.wikipedia['found'][name]
                    self.wikipedia['not_found'].add(name)
                    corrected.add(name)

                to_correct, corrected = to_correct.difference(corrected), set()
                print("Fifth step over, still {} to correct (on {})".format(len(to_correct),
                                                                            len(self.wikipedia['found'])))

        except KeyboardInterrupt:
            print("Keyboard interruption, saving the results...")

    # endregion

    # region Cleaning methods

    @Verbose("Cleaning the database's articles...")
    @Attribute('articles')
    def clean_articles(self, criterion=None, to_del=None, to_keep=None):
        """
        Removes from the database the articles which meet the Article's criterion or whose ids are in to_del or are not
        in to_keep.

        Args:
            criterion: function, criterion that an article must meet to be removed.
            to_del: set, ids of the articles that must be removed.
            to_keep: set, ids of the articles that must be kept.
        """

        if criterion is not None and to_del is None and to_keep is None:
            print("Criterion: {}".format([line for line in criterion.__doc__.splitlines() if line][0][8:]))
            to_del = set()

            for id_ in self.articles:
                if criterion(self.articles[id_]):
                    to_del.add(id_)

        elif criterion is None and to_del is not None and to_keep is None:
            print("Criterion: remove the designated articles.")

        elif criterion is None and to_del is None and to_keep is not None:
            print("Criterion: keep only the designated articles.")
            to_del = set()

            for id_ in self.articles:
                if id_ not in to_keep:
                    to_del.add(id_)

        else:
            raise Exception("Either a criterion or to_del or to_keep must be specified.")

        for id_ in to_del:
            del self.articles[id_]

    @Verbose("Cleaning the database's tuples...")
    @Attribute('tuples')
    def clean_tuples(self, to_del=None, to_keep=None):
        """
        Removes from the database the tuples whose names are in to_del or are not in to_keep.

        Args:
            to_del: set, names of the tuples that must be removed.
            to_keep: set, names of the tuples that must be kept.
        """

        if to_del is not None and to_keep is None:
            print("Criterion: remove the designated tuples.")
            tuples = self.tuples
            self.tuples = []

            for tuple_ in tuples:
                if str(tuple_) not in to_del:
                    self.tuples.append(tuple_)

        elif to_del is None and to_keep is not None:
            print("Criterion: keep only the designated tuples.")
            tuples = self.tuples
            self.tuples = []

            for tuple_ in tuples:
                if str(tuple_) in to_keep:
                    self.tuples.append(tuple_)

        else:
            raise Exception("Either to_del or to_keep must be specified.")

    @Verbose("Cleaning the database's entities...")
    @Attribute('entities')
    def clean_entities(self, to_del=None, to_keep=None):
        """
        Removes from the database the entities whose names are in to_del or are not in to_keep.

        Args:
            to_del: set, names of the entities that must be removed.
            to_keep: set, names of the entities that must be kept.
        """

        if to_del is not None and to_keep is None:
            print("Criterion: remove the designated entities.")

        elif to_del is None and to_keep is not None:
            print("Criterion: keep only the designated entities.")
            to_del = set()

            for name in self.entities:
                if name not in to_keep:
                    to_del.add(name)

        else:
            raise Exception("Either to_del or to_keep must be specified.")

        for name in to_del:
            del self.entities[name]

    @Verbose("Filtering the articles, tuples and entities...")
    def filter(self, min_articles=None, min_queries=None):
        """
        Filter out the articles that doesn't respect the specified threshold on the minimum number of articles or the
        minimum number of queries.

        Args:
            min_articles: int, minimum number of articles an entities' tuple must be in.
            min_queries: int, minimum number of Queries an entities' tuple must have.
        """

        to_keep_articles, to_keep_tuples, to_keep_entities = set(), set(), set()

        if min_articles is not None and min_queries is None:
            print("Minimum number of articles: {}".format(min_articles))
            threshold = min_articles
            attribute = 'article_ids'
        elif min_articles is None and min_queries is not None:
            print("Minimum number of queries: {}".format(min_queries))
            threshold = min_queries
            attribute = 'query_ids'
        else:
            raise Exception("Either min_articles or min_queries must be specified.")

        for tuple_ in self.tuples:
            if len(getattr(tuple_, attribute)) >= threshold:
                to_keep_tuples.add(str(tuple_))
                to_keep_articles.update(tuple_.article_ids)
                to_keep_entities.update([str(entity) for entity in tuple_.entities])

        self.clean_tuples(to_keep=to_keep_tuples)
        self.clean_articles(to_keep=to_keep_articles)
        self.clean_entities(to_keep=to_keep_entities)

        self.min_articles = min_articles if min_articles is not None else self.min_articles
        self.min_queries = min_queries if min_queries is not None else self.min_queries

    # endregion

    # region File methods

    def prefix_suffix(self):
        """
        Returns the standard beginning and ending for a file path.

        Returns:
            prefix: str, beginning of the name of the file (until the name of the folder).
            suffix: str, ending of the name of the file (after the basic name of the file).
        """

        prefix, suffix = '../results/', ''

        if self.max_size is None:
            suffix += '_sizemax'
        elif self.max_size >= 1000:
            suffix += '_size' + str(self.max_size // 1000) + 'k'
        else:
            suffix += '_size' + str(self.max_size)

        if self.shuffle:
            suffix += '_shuffle'

        if self.min_articles is not None:
            suffix += '_articles' + str(self.min_articles)
        if self.min_queries is not None:
            suffix += '_queries' + str(self.min_queries)

        if self.random_seed is not None:
            suffix += '_seed' + str(self.random_seed)

        return prefix, suffix

    def save_pkl(self, attribute_name=None, obj=None, file_name=None, folder_name='queries'):
        """
        Save an attribute (designated by its name) or an object into a file using pickle.

        Args:
            attribute_name: str, name of the attribute to save; if None, save an object instead.
            obj: unk, object saved if no attribute name is provided.
            file_name: str, name of the file; if None, save an attribute with the standard name.
            folder_name: str, name of the folder to save in.
        """

        if attribute_name is not None:
            obj = getattr(self, attribute_name)
        if obj is None:
            raise Exception("Nothing to save, object is None.")

        prefix, suffix = self.prefix_suffix()

        if file_name is not None:
            file_name = prefix + folder_name + '/' + file_name + '.pkl'
        else:
            if attribute_name is not None:
                file_name = prefix + folder_name + '/' + attribute_name + suffix + '.pkl'
            else:
                raise Exception("Missing file name to save the object.")

        try:
            with open(file_name, 'wb') as f:
                dump(obj=obj, file=f, protocol=-1)

            if attribute_name is not None:
                print("Attribute {} saved at {}.".format(attribute_name, file_name))
            else:
                print("Object saved at {}.".format(file_name))

        except PicklingError:
            print("Could not save (PicklingError).")

    def load_pkl(self, attribute_name=None, file_name=None, folder_name='queries'):
        """
        Load an attribute (designated by its name) or an object from a file using pickle.

        Args:
            attribute_name: str, name of the attribute to load; if None, returns the object.
            file_name: str, name of the file to load; if None, load the file with the corresponding standard name.
            folder_name: str, name of the folder to load from.
        """

        prefix, suffix = self.prefix_suffix()

        if file_name is not None:
            file_name = prefix + folder_name + '/' + file_name + '.pkl'
        else:
            if attribute_name is not None:
                file_name = prefix + folder_name + '/' + attribute_name + suffix + '.pkl'
            else:
                raise Exception("Missing file name to load the object.")

        with open(file_name, 'rb') as f:
            obj = load(f)

        if attribute_name is not None:
            print("Attribute {} loaded from {}.".format(attribute_name, file_name))
            setattr(self, attribute_name, obj)
        else:
            print("Object loaded from {}".format(file_name))
            return obj

    def save_csv(self, attribute_name=None, file_name=None, folder_name='queries', limit=None, random_seed=None):
        """
        Save a dictionary attribute to a .csv using pandas DataFrame.

        Args:
            attribute_name: str, name of the attribute to save.
            file_name: str, name of the file; if None, save an attribute with the standard name.
            folder_name: str, name of the folder to save in.
            limit: int, maximum number of data to save; if None, save all of them.
            random_seed: int, the seed to use for the random processes.
        """

        obj = getattr(self, attribute_name)
        ids = sorted(obj.keys())

        if limit is not None:
            if random_seed is not None:
                seed(random_seed)

            shuffle(ids)
            ids = ids[:limit]

        data = [obj[id_].to_html() for id_ in ids]
        df = DataFrame.from_records(data=data)

        prefix, suffix = self.prefix_suffix()

        if file_name is not None:
            file_name = prefix + folder_name + '/' + file_name + '.pkl'
        else:
            file_name = attribute_name if limit is None else attribute_name + '_short'
            file_name = prefix + folder_name + '/' + file_name + suffix + '.csv'

        df.to_csv(file_name, index=False)

        print("Attribute {} saved at {}".format(attribute_name, file_name))

    def write_debug(self, field, method):
        """
        Write the debugging of a method into a text file.

        Args:
            field: str, field of the database we want to debug.
            method: str, name of the method to debug.
        """

        if field == 'articles':
            lines = [[id_, getattr(article, 'debug_' + method)()] for id_, article in self.articles.items()]

        elif field == 'entities':
            lines = [[name, entity.debug_entities()] for name, entity in self.entities.items()]

        elif field == 'tuples':
            lines = [[str(tuple_), tuple_.debug_tuples()] for tuple_ in self.tuples]

        elif field == 'wikipedia':
            lines = [[name, wikipedia.debug_wikipedia()] for name, wikipedia in self.wikipedia['found'].items()] \
                    + [[name, ': not found'] for name in self.wikipedia['not_found']]

        elif field == 'queries':
            lines = [[id_, query.debug_queries()] for id_, query in self.queries.items()]

        else:
            raise Exception("Wrong field/method specified: {}/{}.".format(field, method))

        lines = [line[0] + line[1] + '\n' for line in lines if line[1]]

        if lines:
            prefix, _ = self.prefix_suffix()
            file_name = prefix + 'debug/' + method + '.txt'

            with open(file_name, 'w') as f:
                f.writelines(lines)

            print("Debugging Written in {}...".format(file_name))

    # endregion

    # region Other methods

    @staticmethod
    def progression(count, modulo, size, text):
        """
        Prints progression's updates and update the count.

        Args:
            count: int, current count.
            modulo: int, how often to print updates.
            size: int, size of the element to count.
            text: str, what to print at the beginning of the updates.

        Returns:
            int, incremented count of articles.
        """

        count += 1

        if count % modulo == 0:
            print("   " + text + " {}/{}...".format(count, size))

        return count

    def paths(self):
        """
        Compute the paths of the data files of the database.

        Returns:
            list, sorted file paths of the data of the articles.
        """

        patterns = ['../databases/nyt_jingyun/data/' + str(year) + '/*/*/*.xml' for year in self.years]

        paths = []
        for pattern in patterns:
            paths.extend(glob(pattern))
        paths.sort()

        if self.max_size is not None:
            if self.shuffle:
                shuffle(paths)
                paths = paths[:self.max_size]
                paths.sort()
            else:
                paths = paths[:self.max_size]

        return paths

    @staticmethod
    def subtuples(l):
        """
        Compute all the possible sorted subtuples of len > 1 from a list.

        Args:
            l: list, original list.

        Returns:
            set, all the possible subtuples of len > 1 of l.
        """

        if len(l) < 2:
            return set()

        elif len(l) == 2 or len(l) > 10:
            return {tuple(sorted(l))}

        else:
            res = {tuple(sorted(l))}
            for x in l:
                res = res.union(Database.subtuples([y for y in l if y != x]))

            return res

    @staticmethod
    def plot_hist(fig, data, title, xlabel, log=False):
        """
        Plot the data as a histogram using matplotlib.pyplot. Print the data as well.

        Args:
            fig: int, index of the figure.
            data: numpy.histogram, histogram of the data.
            title: str, title of the figure.
            xlabel: str, label of the x-axis.
            log: bool, whether to use a logarithmic scale or not.
        """

        plt.figure(num=fig, figsize=(12, 4))

        counts, bins = data
        plt.hist(bins[:-1], bins, weights=counts, align='left', rwidth=.8, log=log)
        plt.title(title)
        plt.xlabel(xlabel)

    # endregion


def main():
    database = Database(max_size=1000)

    database.preprocess_database()
    database.process_articles()
    database.process_wikipedia(load=True)

    database.correct_wiki()

    database.process_queries(check_changes=True, csv_seed=1)


if __name__ == '__main__':
    main()
