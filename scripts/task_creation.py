from database_creation.database import Database

max_size = 10000
debug = True

database = Database(max_size=max_size)

database.preprocess_database(debug=debug)
database.process_articles(debug=debug)

database.process_wikipedia(load=True, debug=debug)
database.process_queries(check_changes=True, debug=debug)

database.combine_wiki()

database.correct_wikipedia(step=0)
database.correct_wikipedia(step=1)
database.correct_wikipedia(step=2)
